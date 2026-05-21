"""
类别参考文件加载服务

从 prompts/references/ 目录加载 YAML frontmatter 格式的参考文件，
为 prompt 框架提供类别元数据和 schema 定义。
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class SchemaField(BaseModel):
    """Schema 字段定义"""
    name: str
    type: str
    values: Optional[List[str]] = None
    required: bool


class ReferenceMeta(BaseModel):
    """参考文件元数据"""
    id: str
    version: str
    schema_fields: List[SchemaField]
    generation_hints: Dict  # must_include_sections: list
    features_db: Optional[str] = None
    reference_text: str


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REFERENCES_DIR = Path(__file__).resolve().parent.parent.parent / "prompts" / "references"

_FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def load_category_index() -> dict:
    """读取 prompts/references/_index.json 并返回解析后的字典"""
    index_path = _REFERENCES_DIR / "_index.json"
    with open(index_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_reference_meta(category_id: str) -> ReferenceMeta:
    """
    根据类别 ID 加载参考文件元数据。

    1. 从 _index.json 查找对应的 reference_file
    2. 读取 .md 文件并解析 YAML frontmatter
    3. 返回 ReferenceMeta 实例
    """
    index = load_category_index()

    category_entry = None
    for cat in index.get("categories", []):
        if cat["id"] == category_id:
            category_entry = cat
            break

    if category_entry is None:
        raise ValueError(f"Unknown category_id: {category_id}")

    reference_file = category_entry["reference_file"]
    file_path = _REFERENCES_DIR / reference_file

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    match = _FRONTMATTER_PATTERN.match(content)
    if not match:
        raise ValueError(f"No YAML frontmatter found in {reference_file}")

    frontmatter_text = match.group(1)
    reference_text = content[match.end():]

    import yaml
    frontmatter = yaml.safe_load(frontmatter_text)

    schema_fields = [
        SchemaField(**field) for field in frontmatter.get("schema_fields", [])
    ]

    return ReferenceMeta(
        id=frontmatter["id"],
        version=str(frontmatter["version"]),
        schema_fields=schema_fields,
        generation_hints=frontmatter.get("generation_hints", {}),
        features_db=frontmatter.get("features_db"),
        reference_text=reference_text,
    )


def build_schema_section(reference_meta: ReferenceMeta) -> str:
    """
    根据 schema_fields 生成 OUTPUT_SCHEMA 文本描述。

    - object 类型显示 "{status, comment, evidence}"
    - enum 类型显示可选值列表
    - array 类型显示 "string[]"
    - required 字段标注 ", required"
    """
    lines = []
    for field in reference_meta.schema_fields:
        if field.type == "object":
            type_desc = "{status, comment, evidence}"
        elif field.type == "enum":
            if field.values:
                type_desc = "[" + ", ".join(field.values) + "]"
            else:
                type_desc = "enum"
        elif field.type == "array":
            type_desc = "string[]"
        else:
            type_desc = field.type

        suffix = ", required" if field.required else ""
        lines.append(f"- {field.name}: {type_desc}{suffix}")

    return "\n".join(lines)


def estimate_tokens(text: str) -> int:
    """
    估算文本的 token 数量。

    优先使用 tiktoken，不可用时退化为启发式估算：
    中文字符数 * 0.5 + 英文单词数 * 1.3
    """
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        chinese_chars = len(re.findall(r"[一-鿿]", text))
        english_words = len(re.findall(r"[a-zA-Z]+", text))
        return int(chinese_chars * 0.5 + english_words * 1.3)


def calculate_max_output_tokens(reference_meta: ReferenceMeta, category_entry: dict) -> int:
    """
    计算最大输出 token 数。

    target = max(reference_tokens * 1.6, category max_output_tokens, 1500)
    return min(target, 8000)
    """
    ref_tokens = estimate_tokens(reference_meta.reference_text)
    target = max(
        ref_tokens * 1.6,
        category_entry.get("max_output_tokens", 2000),
        1500,
    )
    return min(int(target), 8000)
