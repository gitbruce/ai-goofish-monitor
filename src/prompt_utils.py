import json
import os
from typing import Awaitable, Callable, Optional

import aiofiles

from src.infrastructure.external.ai_client import AIClient
from src.services.category_router import route_category
from src.services.criteria_validator import validate_criteria, should_retry
from src.services.reference_loader import (
    ReferenceMeta,
    build_schema_section,
    calculate_max_output_tokens,
    load_category_index,
    load_reference_meta,
)

CRITERIA_GENERATION_PROMPT = """你是一位世界级的AI提示词工程大师。你的任务是根据用户提供的【购买需求】，参照一份【品类参考库】，为闲鱼监控机器人的AI分析模块（代号 EagleEye-V7）生成一份全新的【分析标准】文本。

以下是【品类参考库】（{category_id}）：
```text
{reference_text}
```

这是用户的【购买需求】：
```text
{user_description}
```

请现在开始生成全新的【分析标准】文本。请注意：
1. **只输出新生成的文本内容**，不要包含任何额外的解释、标题或代码块标记。
2. 严格遵循参考库中的所有章节结构和核心原则。
3. 将参考库中的通用内容，替换为与用户需求商品相关的内容。
4. 必须包含参考库 generation_hints 中指定的所有章节。
5. 必须在文本中提及参考库 schema_fields 中的所有字段名称。
"""

ProgressCallback = Callable[[str, str], Awaitable[None]]


async def _report_progress(
    progress_callback: Optional[ProgressCallback],
    step_key: str,
    message: str,
) -> None:
    if progress_callback:
        await progress_callback(step_key, message)


async def _request_generated_text(
    ai_client: AIClient,
    prompt: str,
    max_output_tokens: int = 2000,
) -> str:
    print(f"正在调用AI生成分析标准（max_tokens={max_output_tokens}），请稍候...")
    try:
        generated_text = await ai_client._call_ai(
            [{"role": "user", "content": prompt}],
            temperature=0.5,
            max_output_tokens=max_output_tokens,
            enable_json_output=False,
        )
    except Exception as exc:
        print(f"调用 AI API 时出错: {exc}")
        raise

    print("AI已成功生成内容。")
    return generated_text.strip()


async def _close_ai_client(
    ai_client: AIClient,
    active_error: BaseException | None,
) -> None:
    try:
        await ai_client.close()
    except Exception as close_error:
        print(f"关闭 AI 客户端时出错: {close_error}")
        if active_error is None:
            raise


async def generate_criteria(
    user_description: str,
    reference_file_path: str = "",
    progress_callback: Optional[ProgressCallback] = None,
    category_id: str | None = None,
) -> tuple[str, str]:
    """
    Generates criteria text using the category-aware pipeline.

    Pipeline: CategoryRouter → ReferenceLoader → CriteriaGenerator → Validator

    Returns:
        tuple of (generated_criteria_text, category_id)
    """
    ai_client = AIClient()
    active_error: BaseException | None = None
    try:
        if not ai_client.is_available():
            ai_client.refresh()
        if not ai_client.is_available():
            raise RuntimeError("AI客户端未初始化，无法生成分析标准。请检查.env配置。")

        # Step 1: Route category (if not explicitly provided)
        if not category_id:
            await _report_progress(progress_callback, "route", "正在识别商品品类。")
            route_result = await route_category(user_description, ai_client)
            category_id = route_result.category
            print(f"品类路由结果: category={category_id}, confidence={route_result.confidence}, reasoning={route_result.reasoning}")
        else:
            print(f"使用指定品类: {category_id}")

        # Step 2: Load reference
        await _report_progress(progress_callback, "reference", "正在加载品类参考库。")
        try:
            reference_meta = load_reference_meta(category_id)
        except (ValueError, FileNotFoundError) as exc:
            print(f"参考库加载失败({category_id})，回退到 generic: {exc}")
            category_id = "generic"
            reference_meta = load_reference_meta(category_id)

        # Step 3: Calculate max_output_tokens
        index = load_category_index()
        category_entry = next(
            (c for c in index.get("categories", []) if c["id"] == category_id),
            {},
        )
        max_tokens = calculate_max_output_tokens(reference_meta, category_entry)

        # Step 4: Build prompt
        await _report_progress(progress_callback, "prompt", "正在构建发送给 AI 的指令。")
        prompt = CRITERIA_GENERATION_PROMPT.format(
            category_id=category_id,
            reference_text=reference_meta.reference_text,
            user_description=user_description,
        )

        # Step 5: Generate
        await _report_progress(progress_callback, "llm", "正在调用 AI 生成分析标准。")
        generated_text = await _request_generated_text(ai_client, prompt, max_tokens)

        # Step 6: Validate and optionally retry
        report = validate_criteria(generated_text, reference_meta, category_id)
        print(f"校验结果: valid={report.is_valid}, truncation={report.truncation_detected}, "
              f"missing_sections={report.missing_sections}, missing_fields={report.missing_schema_fields}")

        if should_retry(report):
            print("校验未通过，以 1.5x tokens 重试一次...")
            retry_tokens = min(int(max_tokens * 1.5), 8000)
            generated_text = await _request_generated_text(ai_client, prompt, retry_tokens)

            report = validate_criteria(generated_text, reference_meta, category_id)
            print(f"重试校验结果: valid={report.is_valid}")

        if report.warnings:
            for w in report.warnings:
                print(f"  警告: {w}")

        return generated_text, category_id

    except Exception as exc:
        active_error = exc
        raise
    finally:
        await _close_ai_client(ai_client, active_error)


async def update_config_with_new_task(new_task: dict, config_file: str = "config.json"):
    """
    将一个新任务添加到指定的JSON配置文件中。
    """
    print(f"正在更新配置文件: {config_file}")
    try:
        config_data = []
        if os.path.exists(config_file):
            async with aiofiles.open(config_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                if content.strip():
                    try:
                        config_data = json.loads(content)
                        print(f"成功读取现有配置，当前任务数量: {len(config_data)}")
                    except json.JSONDecodeError as e:
                        print(f"解析配置文件失败，将创建新配置: {e}")
                        config_data = []
        else:
            print(f"配置文件不存在，将创建新文件: {config_file}")

        config_data.append(new_task)

        async with aiofiles.open(config_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(config_data, ensure_ascii=False, indent=2))
            print(f"配置文件写入完成")

        print(f"成功！新任务 '{new_task.get('task_name')}' 已添加到 {config_file} 并已启用。")
        return True
    except json.JSONDecodeError as e:
        error_msg = f"错误: 配置文件 {config_file} 格式错误，无法解析: {e}"
        import sys
        sys.stderr.write(error_msg + "\n")
        print(error_msg)
        return False
    except IOError as e:
        error_msg = f"错误: 读写配置文件失败: {e}"
        import sys
        sys.stderr.write(error_msg + "\n")
        print(error_msg)
        return False
    except Exception as e:
        error_msg = f"错误: 更新配置文件时发生未知错误: {e}"
        import sys
        sys.stderr.write(error_msg + "\n")
        print(error_msg)
        import traceback
        print(traceback.format_exc())
        return False
