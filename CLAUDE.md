# ai-goofish-monitor - Agent Working Agreement

## Project Context

- Summary: 基于 Playwright + AI 的闲鱼智能监控机器人。FastAPI 后端 + Vue 3 前端，支持多任务并发监控、多模态 AI 商品分析、多渠道通知推送。
- Primary goal: 爬虫监控管道 + AI 评估 + 通知推送全链路稳定运行。
- Main users: 闲鱼买家 / 二手交易监控使用者。
- Constraint: Do not revert existing user changes. Do not commit real `.env` values, login state, scraped data, or local runtime residue.

## Runtime Profile

- Backend: Python (FastAPI + uvicorn + APScheduler + Playwright).
- Frontend: Vue 3 + Vite + shadcn-vue + Tailwind CSS (`web-ui/`).
- Local ports: 后端 `8000`（可通过 `SERVER_PORT` 环境变量覆盖）.
- Startup entrypoint: `./start.sh`（前端构建 + 后端启动）.
- Docker: `docker compose up --build -d`.

## Source Of Truth

1. Current repository files and git state.
2. `CLAUDE.md` for project instructions and conventions.
3. `AGENTS.md` for coding standards, commit/PR rules, and testing guidance.
4. `config.json` for task definitions, `.env` for secrets and runtime flags.
5. `prompts/` for AI prompt framework (base prompt, references, tasks).

## Verification

```bash
pytest                    # 运行所有测试
pytest --cov=src          # 覆盖率报告
ruff check .              # Lint
ruff check --fix .        # Lint 自动修复
```

测试规范：文件 `tests/**/test_*.py`，函数 `test_*`。PR 前请运行相关测试。

## Workspace Hygiene

This section is extensible. Add new rules as bullets below; later rules supplement earlier ones. Agents must read this section before creating files or branches.

- Use `.worktrees/` for isolated parallel work, experimental branches, or risky refactors. Do not pile divergent changes onto the main checkout; create a worktree, do the work, then merge or discard.
- Do not create temporary files, scratch reports, ad-hoc logs, debug dumps, or one-off agent outputs in the repository root. Generated reports belong under `outputs/` (ignored except `outputs/.gitkeep`).
- `.worktrees/`, `.claude/`, `.multipowers/`, `.omc/`, and tool runtime directories are local residue. They must remain ignored and must not be committed.
- Before editing files, check `git status --short` and preserve unrelated user changes.

## Artifact Policy

- Track: `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `README.md`, source code, `prompts/base_prompt.txt`, `prompts/references/`, `web-ui/` frontend sources.
- Ignore: `.env`, `config.json`, `state.json`, `xianyu_state.json`, local logs, `outputs/*` except `outputs/.gitkeep`, `images/`, `logs/`, `jsonl/`, `dist/`, `__pycache__/`, `data/`, `price_history/`, and generated runtime artifacts.

## Local Environment Notes

When running git network operations from WSL, use the host proxy first. Standard pattern:

```bash
host_ip=$(ip route show | grep -i default | awk '{print $3}')
export http_proxy="http://$host_ip:7890"
export https_proxy="http://$host_ip:7890"
```

Apply this before `git fetch`, `git pull`, `git push`, or other remote git operations when the WSL environment does not have direct network access.

## 核心架构

```
API层 (src/api/routes/)
    ↓
服务层 (src/services/)
    ↓
领域层 (src/domain/)
    ↓
基础设施层 (src/infrastructure/)
```

关键入口：
- `src/app.py` - FastAPI 应用主入口
- `spider_v2.py` - 爬虫 CLI 入口
- `src/scraper.py` - Playwright 爬虫核心逻辑

服务层：
- `TaskService` - 任务 CRUD
- `ProcessService` - 爬虫子进程管理
- `SchedulerService` - APScheduler 定时调度
- `AIAnalysisService` - 多模态 AI 分析
- `NotificationService` - 多渠道通知（ntfy/Bark/企业微信/Telegram/Webhook）
- `CategoryRouter` - AI 品类路由（user_description → category_id）
- `ReferenceLoader` - 品类参考库加载（YAML frontmatter + schema）
- `CriteriaValidator` - 生成标准完整性校验（截断/章节/字段/噪声）

## 开发命令

```bash
# 后端开发
python -m src.app
# 或
uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload

# 前端开发
cd web-ui && npm install && npm run dev

# 前端构建
cd web-ui && npm run build

# 一键本地启动（构建前端 + 启动后端）
bash start.sh

# Docker 部署
docker compose up --build -d
```

## 爬虫命令

```bash
python spider_v2.py                          # 运行所有启用任务
python spider_v2.py --task-name "MacBook"    # 运行指定任务
python spider_v2.py --debug-limit 3          # 调试模式，限制商品数
python spider_v2.py --config custom.json     # 自定义配置文件
```

## 配置

环境变量 (`.env`)：
- AI 模型：`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL_NAME`
- 通知：`NTFY_TOPIC_URL`, `BARK_URL`, `WX_BOT_URL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- 爬虫：`RUN_HEADLESS`, `LOGIN_IS_EDGE`
- Web 认证：`WEB_USERNAME`, `WEB_PASSWORD`
- 端口：`SERVER_PORT`

任务配置 (`config.json`)：定义监控任务（关键词、价格范围、cron 表达式、AI prompt 文件等）

## 数据流

1. Web UI / config.json 创建任务
2. CategoryRouter 路由用户需求到品类（bicycle.road / digital.laptop / generic）
3. ReferenceLoader 加载品类参考库 + schema 定义
4. AI 生成品类专属 criteria（动态 max_output_tokens）→ Validator 校验
5. Criteria 落盘至 `prompts/tasks/{keyword}.txt`
6. SchedulerService 按 cron 触发或手动启动
7. spider_v2.py 运行时：加载 criteria + build_schema_section() 注入 {{OUTPUT_SCHEMA}}
8. AIAnalysisService 调用多模态模型分析
9. NotificationService 推送符合条件的商品
10. 结果存储：`jsonl/`（数据）、`images/`（图片）、`logs/`（日志）

## Prompt 框架目录结构

```
prompts/
  base_prompt.txt              ← EagleEye-V7，含 {{CRITERIA_SECTION}} + {{OUTPUT_SCHEMA}}
  references/                  ← 品类参考库（YAML frontmatter）
    _index.json                ← 品类路由索引
    bicycle.road.md            ← 公路自行车参考（12 schema fields）
    digital.laptop.md          ← 笔记本电脑参考
    _generic.md                ← 通用兜底参考
    bicycle.road.features/     ← 真品特征库
      sl8.md                   ← Specialized Tarmac SL8
      propel_sl.md             ← Giant Propel Advanced SL
  tasks/                       ← AI 生成的 criteria 落地位置
  _archive/                    ← 旧版 *_criteria.txt 备份
```

扩展品类：在 `prompts/references/` 加文件 + 更新 `_index.json`，无需改代码。

## 注意事项

- AI 模型必须支持图片上传（多模态）
- Docker 部署需通过 Web UI 手动更新登录状态（`state.json`）
- 遇到滑动验证码时设置 `RUN_HEADLESS=false` 手动处理
- 生产环境务必修改默认 Web 认证密码
