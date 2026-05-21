# Prompt 框架升级与自行车深度方案 — 设计文档

- **日期**：2026-05-20
- **版本**：V7 设计草案
- **范围**：通用品类化升级 + 自行车（公路车）深度方案
- **不在范围**：Web UI 视觉改造、通知模块、数据库迁移工具

---

## 1. 背景与动机

当前实现存在以下结构性问题：

1. **生成截断**：`src/prompt_utils.py` 中 `max_output_tokens=800` 导致 `prompts/闪电sl8_criteria.txt`、`prompts/ppsl_criteria.txt` 实际只生成到 25 行，第二部分卖家深度画像、邮寄、信用细则全部丢失。
2. **参考范例硬编码**：所有品类的 criteria 都以 `prompts/macbook_criteria.txt` 为模板，自行车场景丢失"组装/淘宝架/翻新喷漆/拆车件"等本地化红旗信号。
3. **输出 schema 与品类错位**：`prompts/base_prompt.txt` 内的 JSON schema 固定包含 `model_chip`、`battery_health` 等数码字段，与自行车 criteria 中 `model_spec`、`groupset`、`size_geometry` 字段相互污染。
4. **自行车场景维度缺失**：盗抢来源、真品特征、组装/喷漆改装、车架与整车形态分支、价格-公允价交叉校验、专业打包/验车策略等均未在现行 criteria 中体现。
5. **无完整性校验**：截断、字段缺失、章节缺失会静默落盘，没有任何告警。

本次升级目标：
- 通用：把 prompt 生成从"单模板硬编码"升级为"品类路由 + 参考库 + 动态 schema + 完整性校验"。
- 深度：为自行车（公路车）场景给出真品特征库、商品形态自适应、自行车专属 schema。
- 自动化：max_output_tokens 按品类与参考长度动态计算，避免再次截断。
- 识别率：通过真品特征库 + 红旗本地化词表显著提升伪冒/拼装识别。

---

## 2. 架构总览

### 2.1 任务创建流程

```
用户需求 (user_description)
  → ① CategoryRouter (AI 轻量调用, JSON 输出)
      → {category, subtype, confidence, reasoning}
  → ② ReferenceLoader (按 category 读 prompts/references/<id>.md)
      → reference_text + schema_fragment + features_db_path
  → ③ CriteriaGenerator (AI 主调用, 动态 max_output_tokens)
      → criteria.txt
  → ④ Validator (完整性 / 字段 / 章节校验)
      → 通过 ⇒ 落盘 prompts/tasks/<safe_keyword>.txt
      → 失败 ⇒ 1.5× tokens 重试 1 次; 仍失败则标记 incomplete=true
```

### 2.2 运行时流程

```
spider_v2.py
  → 读 task 的 category_id 与 criteria_file
  → 读 prompts/references/<id>.md frontmatter 取 schema_fields
  → build_schema_section() 生成 OUTPUT_SCHEMA 文本
  → base_prompt.txt.replace({{CRITERIA_SECTION}}, criteria_text)
                  .replace({{OUTPUT_SCHEMA}}, schema_section)
  → 送入多模态 AI → 输出按 criteria 自适应字段的 JSON
```

### 2.3 关键变化点（vs 当前实现）

| 模块 | 当前 | 升级后 |
|---|---|---|
| 参考范例 | 硬编码 `macbook_criteria.txt` | 多份参考库，AI 路由 |
| max_output_tokens | 固定 800 | 按参考长度 × 1.6 动态，下限/上限保护 |
| 输出 schema | base_prompt 硬编码数码字段 | 参考库 frontmatter 声明，运行时注入 |
| 完整性 | 无 | Validator + 自动重试 |
| 品类扩展 | 改代码 | 在 `prompts/references/` 加文件 |

### 2.4 目录结构

```
prompts/
  base_prompt.txt                  ← 改为含 {{OUTPUT_SCHEMA}} 占位符
  references/
    _index.json                    ← 路由用：枚举可用 category
    bicycle.road.md                ← 自行车参考库（含 schema frontmatter）
    bicycle.road.features/         ← 真品特征库
      sl8.md
      propel_sl.md
      tarmac_sl7.md
      madone.md                    ← 后续按需扩展
    digital.laptop.md              ← 由 macbook_criteria 迁移而来
    digital.phone.md
    _generic.md                    ← confidence < 0.6 时兜底
  tasks/                           ← 生成的 criteria 落地位置
    macbook.txt
    sl8.txt
    ppsl.txt
  _archive/                        ← 旧版 *_criteria.txt 备份
```

---

## 3. 品类路由器（CategoryRouter）

### 3.1 输入

```python
class RouteRequest:
    user_description: str
    index_summaries: list[dict]  # 从 _index.json 提取
```

### 3.2 Prompt 模板

```
你是品类路由器。下面是可选品类清单，每项含 1 行摘要：
{index_summaries}

用户需求：{user_description}

请只输出 JSON：
{
  "category": "<必须在清单 id 内, 不能编造>",
  "confidence": 0.0-1.0,
  "reasoning": "<不超过20字>"
}
若无法归入任何品类，category 返回 "generic"。
```

> 注：本版本不引入 `subtype` 字段；型号粒度的差异由参考库正文中的 features_db 在主调用阶段处理。后续若需要按 subtype 预筛 features 文件，再扩展路由 schema。

### 3.3 调用配置

- `temperature=0.0`
- `max_output_tokens=200`
- `enable_json_output=True`

### 3.4 降级规则

- `confidence < 0.6` ⇒ 回退到 `generic`
- Web UI 在路由结果展示 confidence，允许用户手动覆盖

---

## 4. 参考库格式

每个 `references/<id>.md` 由 YAML frontmatter + 正文构成。

### 4.1 Frontmatter 必需字段

```yaml
---
id: bicycle.road
version: 1.0
schema_fields:
  - {name: product_form,         type: enum,   values: [frameset, complete_bike, ambiguous], required: true}
  - {name: model_version,        type: object, required: true}
  - {name: frame_size_fit,       type: object, required: true}
  - {name: groupset_wheels,      type: object, required: true}
  - {name: frame_condition,      type: object, required: true}
  - {name: crash_repair_history, type: object, required: true}
  - {name: provenance_serial,    type: object, required: true}
  - {name: authenticity,         type: object, required: true}
  - {name: seller_type,          type: object, required: true}
  - {name: shipping_inspection,  type: object, required: true}
  - {name: price_value,          type: object, required: true}
  - {name: manual_questions,     type: array,  required: true}
generation_hints:
  must_include_sections:
    - "第一部分：核心分析原则"
    - "第二部分：商品形态判定"
    - "第三部分：按形态分支的字段适用矩阵"
    - "第四部分：真品特征校验清单"
    - "第五部分：详细分析指南"
    - "第六部分：危险信号与豁免条款"
    - "第七部分：manual_questions 生成指南"
features_db: bicycle.road.features/
---
```

### 4.2 `_index.json` 格式

```json
{
  "categories": [
    {
      "id": "bicycle.road",
      "summary": "二手公路自行车（整车或车架），含闪电Tarmac/SL系列、捷安特Propel、Trek Madone等运动级公路车",
      "keywords_hint": ["公路车", "SL8", "Propel", "Madone", "Ultegra"],
      "reference_file": "bicycle.road.md",
      "max_output_tokens": 3000
    },
    {
      "id": "digital.laptop",
      "summary": "二手笔记本电脑，含 MacBook / ThinkPad / 游戏本",
      "keywords_hint": ["MacBook", "笔记本", "ThinkPad"],
      "reference_file": "digital.laptop.md",
      "max_output_tokens": 2000
    },
    {
      "id": "generic",
      "summary": "通用二手商品（兜底）",
      "reference_file": "_generic.md",
      "max_output_tokens": 2000
    }
  ]
}
```

---

## 5. 动态 max_output_tokens 策略

### 5.1 公式

```python
target = max(
    reference_length_tokens * 1.6,
    category.max_output_tokens,
    1500,
)
final_tokens = min(target, 8000)
```

### 5.2 Token 测量

- 优先使用 `tiktoken`（OpenAI 通用 BPE）
- 缺省时回退 `len(text_zh) * 0.5 + len(text_en_words) * 1.3`

### 5.3 重试策略

- Validator 检出截断 / 缺章节 ⇒ 用 `1.5 × current_tokens` 重试 1 次
- 二次失败 ⇒ 原文落盘 + `task.incomplete = True` + Web UI 红色 badge

### 5.4 各品类下限

| 品类 | 下限 (tokens) |
|---|---|
| bicycle.road | 3000 |
| digital.laptop | 2000 |
| digital.phone | 2000 |
| apparel.sneaker | 2500 |
| generic | 2000 |

---

## 6. 自行车深度方案

### 6.1 `bicycle.road.md` 正文结构

```
第一部分：核心分析原则
  1. 画像优先原则
  2. 一票否决硬性原则（按 product_form 分支）
  3. 图片至上原则
  4. 信息缺失处理原则（NEEDS_MANUAL_CHECK 不直接否决）
  5. 真伪先于一切原则（authenticity = FAIL 不可豁免）

第二部分：商品形态判定（必须先做）
  product_form 判定依据：
    - 标题/描述含"车架/裸架/frameset/仅车架/光架" → frameset
    - 含"整车/原车/套件齐全/可骑/带轮子" → complete_bike
    - 仅图片显示车架且文本未明示 → ambiguous（按 complete_bike 处理但 confidence 降级）

第三部分：按形态分支的字段适用矩阵
  字段                  frameset   complete_bike   ambiguous
  product_form           ✓             ✓             ✓
  model_version          ✓             ✓             ✓
  frame_size_fit         ✓             ✓             ✓
  frame_condition        ✓             ✓             ✓
  crash_repair_history   ✓             ✓             ✓
  authenticity           ✓             ✓             ✓
  provenance_serial      ✓             ✓             ✓
  groupset_wheels       N/A            ✓            可选
  price_value         按裸架公允价    按整车公允价    按整车
  shipping_inspection 强调专业打包    ✓             ✓
  seller_type            ✓             ✓             ✓

第四部分：真品特征校验清单
  对每个声明的型号，AI 必须按 features_db 中的特征文件逐项核对：
    - 头管/上管/下管几何特征
    - Logo 字体、位置、印刷工艺
    - 车架编号格式与位置
    - 走线方式（内走线 / 外走线）
    - 焊接点 / 碳布纹理
    - 后下叉与五通衔接形态
  规则：
    - 任一关键特征"图片不可见" → 该项 NEEDS_MANUAL_CHECK
    - 任一关键特征"明显不符" → authenticity.status = FAIL → 整体 FAIL（不可豁免）

第五部分：详细分析指南
  对 schema 中每个字段，给出 PASS / FAIL / NEEDS_MANUAL_CHECK 判定细则
  关键字段说明：
    - frame_size_fit：综合"车架码 + 卖家身高 + 坐垫高度 + 把立长度 +
      垫圈数 + 坐管外露 + 几何代际"
    - price_value：与该型号年款的市场公允价比对，异常低价 → 强红旗
    - provenance_serial：要求车架编号清晰图，缺失或被遮挡 → 强红旗

第六部分：危险信号与豁免条款
  红旗清单（自行车圈本地化）：
    组装车、淘宝架、翻新喷漆、拆车件、三方上漆、打螺丝快、
    量大从优、同行价、店内一手货源、批发价、可议、量大
  豁免条款（允许的个人玩家行为）：
    自费补漆（小范围）、升级套件、换轮组、换把组、换坐垫、
    多年长期持有、骑行内容丰富

第七部分：manual_questions 生成指南
  把所有缺失或需追问的项汇总到 manual_questions 数组，例如：
    ["车架编号清晰照片", "购车凭证或骑友群证明",
     "BB 下方序列号", "近距离头管侧面照", "原车出厂套件型号"]
```

### 6.2 真品特征文件示例（`features/sl8.md`）

```markdown
# Specialized Tarmac SL8 真品特征

## 关键识别点（按可靠性降序）
1. 头管形状：SL8 头管前缘为非对称 aero cutout（区别于 SL7 平直前缘）
2. 下管 logo：标准 "TARMAC SL8" 印刷，居中略偏后
3. 后下叉：左侧短下叉（DropSeatStay），与 SL7 对称下叉不同
4. 走线：全内走线进入头管，Roval 把组一体化
5. 车架编号：BB 下方，格式 "WSBC" 或 "SBCU" 开头 + 8 位
6. 坐管夹：内嵌式，无外露夹环

## 常见伪冒形态
- 改色喷漆 SL7 车架贴 SL8 logo（下叉对称即漏馅）
- 廉价无标碳架喷涂 Specialized logo（头管形状对不上）
- S-Works SL8 涂掉 S-Works 字样冒充 SL8（重量 / 车架编号可查）

## AI 必须输出（authenticity 子对象）
{
  "head_tube_shape":       {"observed": "...", "matches_genuine": bool, "evidence_image": "..."},
  "logo_consistency":      {"observed": "...", "matches_genuine": bool, "evidence_image": "..."},
  "rear_dropout_asymmetry":{"observed": "...", "matches_genuine": bool, "evidence_image": "..."},
  "serial_visible":        {"observed": "...", "matches_genuine": bool, "evidence_image": "..."},
  "overall_authentic":     bool
}
```

### 6.3 当前两份 criteria 的迁移

- `prompts/闪电sl8_criteria.txt` ⇒ 走 CategoryRouter → `bicycle.road` + `features/sl8.md`，重新生成完整版；保留用户对 54 码、Ultegra Di2 的偏好作为 user_description 输入
- `prompts/ppsl_criteria.txt` ⇒ 同样路由到 `bicycle.road` + `features/propel_sl.md`
- 旧文件备份至 `prompts/_archive/`

---

## 7. base_prompt 与输出 schema 动态化

### 7.1 base_prompt.txt 改造

```text
你是世界顶级的二手交易分析专家，代号 EagleEye-V7。

{{CRITERIA_SECTION}}

### 第三部分：输出格式（必须严格遵守）

你的输出必须是以下 JSON 对象，字段定义如下：

{{OUTPUT_SCHEMA}}

通用字段（所有品类共有）：
- prompt_version: string
- is_recommended: boolean
- reason: string
- risk_tags: string[]
- manual_questions: string[]
- criteria_analysis: object（具体字段见上方 SCHEMA）
```

### 7.2 schema 注入函数

```python
def build_schema_section(reference_meta: ReferenceMeta) -> str:
    lines = ["criteria_analysis 字段定义："]
    for field in reference_meta.schema_fields:
        suffix = ", required" if field.required else ""
        lines.append(f"  {field.name} ({field.type}{suffix}):")
        if field.type == "object":
            lines.append("    {status, comment, evidence}")
        elif field.type == "enum":
            lines.append(f"    取值: {field.values}")
        elif field.type == "array":
            lines.append("    string[]")
    return "\n".join(lines)
```

### 7.3 运行时拼接

替换 `spider_v2.py:118-128` 现有逻辑：

```python
reference_meta = load_reference_meta(task.category_id)
criteria_text  = read(task.criteria_file)
base_prompt    = read("prompts/base_prompt.txt")
schema_section = build_schema_section(reference_meta)
final_prompt   = (
    base_prompt
    .replace("{{CRITERIA_SECTION}}", criteria_text)
    .replace("{{OUTPUT_SCHEMA}}", schema_section)
)
```

`task` 数据结构新增字段：
- `category_id: str`
- `incomplete: bool = False`

`config.json` 与 SQLite bootstrap 同步：
- `src/domain/models/task.py:Task` 新增字段
- `src/infrastructure/persistence/sqlite_bootstrap.py` 增加迁移逻辑（已有任务默认 `category_id="generic"`）

---

## 8. 完整性校验（Validator）

### 8.1 检查项

| # | 检查项 | 通过条件 | 失败动作 |
|---|---|---|---|
| 1 | 截断检测 | 末尾为完整中文句号 + 字符数 > reference × 0.6 | 1.5× tokens 重试 |
| 2 | 必需章节 | `must_include_sections` 全部出现 | 1.5× tokens 重试 |
| 3 | schema 字段提及 | 每个 `schema_fields.name` 在文本中至少出现 1 次 | 1.5× tokens 重试 |
| 4 | 噪声字段 | 不出现其他品类的字段（如 `battery_health` 出现在自行车 criteria） | 删除噪声段后保留 |
| 5 | 硬性否决条款数 | "一票否决"章节中以序号/项目符号列出的条款 ≥ 3 条（通过解析 Markdown bullet/编号 list 统计） | 警告但不阻断 |

### 8.2 失败处理

- 一次重试：1.5× tokens
- 二次失败：原文落盘 + `task.incomplete=True` + Web UI 红色 badge
- 不静默失败、不静默截断、不静默裁剪

### 8.3 路由置信度低的处理

- `confidence < 0.6` ⇒ Web UI 显示"识别为 generic，建议手动指定品类"
- 提供品类下拉框允许用户覆盖
- 用户选定后重新生成

---

## 9. 影响面与改动清单

### 9.1 新增

- `prompts/references/_index.json`
- `prompts/references/bicycle.road.md`
- `prompts/references/bicycle.road.features/sl8.md`
- `prompts/references/bicycle.road.features/propel_sl.md`
- `prompts/references/digital.laptop.md`（迁移自 macbook_criteria）
- `prompts/references/_generic.md`
- `src/services/category_router.py`
- `src/services/criteria_validator.py`
- `src/services/reference_loader.py`

### 9.2 修改

- `src/prompt_utils.py` —— 重构 meta-prompt 生成入口，调用 router + reference loader + validator
- `src/services/task_generation_runner.py` —— 接入新流水线，移除 macbook 硬编码
- `src/api/routes/tasks.py` —— 接入 category_id；UI 暴露 confidence 与品类下拉
- `prompts/base_prompt.txt` —— 加入 `{{OUTPUT_SCHEMA}}` 占位符
- `spider_v2.py:118-128` —— 运行时拼接两个占位符
- `src/domain/models/task.py` —— 新增 `category_id`、`incomplete` 字段
- `src/infrastructure/persistence/sqlite_bootstrap.py` —— 字段迁移
- `web-ui/` —— 任务创建表单展示路由结果与置信度，允许覆盖

### 9.3 一次性数据迁移

- 已存在的 `prompts/*_criteria.txt` 迁移到 `prompts/tasks/<safe_keyword>.txt`
- 已存在任务在 SQLite 中补齐 `category_id`（自行车类型走 router 一次性回填，其他默认 generic）
- 原文件备份到 `prompts/_archive/`

---

## 10. 验收标准

1. `prompts/references/bicycle.road.md` + features/sl8.md + features/propel_sl.md 全部就位且通过 Validator
2. 重新生成 `tasks/sl8.txt`、`tasks/ppsl.txt`，长度 ≥ 2000 字符，包含全部 7 个章节，包含全部 schema 字段名
3. 运行一次完整爬虫 + AI 分析流程，对 1 条已知正品 + 1 条已知拼装/伪冒样本，AI 输出 JSON 字段与 schema 一致，且伪冒样本 `authenticity.overall_authentic = false`
4. 在 Web UI 中创建一个新自行车任务，路由 confidence ≥ 0.8，生成的 criteria 通过 Validator
5. 在 Web UI 中创建一个新数码任务，路由到 `digital.laptop`，schema 不含自行车字段
6. 故意输入 100 tokens 极限 user_description，触发 Validator 重试逻辑并成功降级或重生成

---

## 11. 不解决的问题（明确范围外）

- 真品特征库的长期维护机制（人工维护，后续可考虑半自动更新）
- 价格公允价的数据源对接（本方案仅要求 AI 给出主观判断，不接入闲鱼历史成交数据）
- 路由器的多语言支持（仅中文）
- features_db 与外部品牌官网的链接校验
