"""
Criteria validation service

Validates generated criteria text for completeness and correctness,
checking for truncation, missing sections, schema field coverage,
noise field leakage, and veto clause quality.
"""
import re
from typing import List

from pydantic import BaseModel

from src.services.reference_loader import ReferenceMeta


class ValidationReport(BaseModel):
    """Result of criteria text validation."""

    is_valid: bool = False
    truncation_detected: bool = False
    missing_sections: List[str] = []
    missing_schema_fields: List[str] = []
    noise_fields: List[str] = []
    veto_clause_count: int = 0
    warnings: List[str] = []


# Noise fields per conflicting category — used to detect content from
# the wrong product category bleeding into generated criteria.
_NOISE_FIELDS: dict[str, list[str]] = {
    "bicycle": [
        "groupset",
        "frame_size_fit",
        "chainring",
        "cassette",
        "handlebar",
        "seatpost",
    ],
    "digital": [
        "battery_health",
        "model_chip",
        "battery",
        "充电",
        "电池",
    ],
    "generic": [],
}


def _detect_truncation(text: str, reference_text: str) -> bool:
    """Return True if the text appears truncated."""
    text = text.strip()
    if not text:
        return True

    # Not truncated if text ends with a complete Chinese period
    if text.endswith("。"):
        return False

    # Not truncated if text ends with a digit
    if text[-1].isdigit():
        return False

    # If text is shorter than 60% of the reference, treat as truncated
    if len(reference_text) > 0 and len(text) < len(reference_text) * 0.6:
        return True

    return False


def _check_required_sections(text: str, must_include_sections: list[str]) -> list[str]:
    """Return section headers that are missing from text."""
    missing: list[str] = []
    for section in must_include_sections:
        if section not in text:
            missing.append(section)
    return missing


def _check_schema_fields(text: str, schema_fields: list) -> tuple[list[str], list[str]]:
    """Return (all_missing, required_missing) schema field names."""
    all_missing: list[str] = []
    required_missing: list[str] = []
    for field in schema_fields:
        if field.name not in text:
            all_missing.append(field.name)
            if field.required:
                required_missing.append(field.name)
    return all_missing, required_missing


def _detect_noise_fields(text: str, category_id: str) -> list[str]:
    """Detect fields from conflicting categories that leaked into text."""
    text_lower = text.lower()

    if category_id.startswith("bicycle"):
        noise_keys = ["digital"]
    elif category_id.startswith("digital"):
        noise_keys = ["bicycle"]
    else:
        noise_keys = ["digital", "bicycle"]

    found: list[str] = []
    for key in noise_keys:
        for field in _NOISE_FIELDS.get(key, []):
            if field in text_lower:
                found.append(field)
    return found


def _count_veto_clauses(text: str) -> tuple[int, list[str]]:
    """Count bullet items in the veto section and return (count, warnings)."""
    warnings: list[str] = []

    # Find the section containing the veto marker
    veto_pos = text.find("一票否决")
    if veto_pos == -1:
        warnings.append("未找到「一票否决」相关章节。")
        return 0, warnings

    # Extract text from veto marker to the next major section header
    # (a line that looks like a ## or === header or end of text)
    remaining = text[veto_pos:]
    lines = remaining.split("\n")

    clause_lines: list[str] = []
    for line in lines[1:]:  # skip the line containing the veto header itself
        stripped = line.strip()
        # Stop at next section header
        if stripped.startswith("##") or stripped.startswith("==="):
            break
        # Count bullet items: lines starting with "- " or numbered "**" markers
        if re.match(r"^\s*[-*]\s", line) or re.match(r"^\s*\d+[.、]\s*\*\*", line):
            clause_lines.append(stripped)

    count = len(clause_lines)
    if count < 3:
        warnings.append(
            f"一票否决条款数量偏少（{count} 条），建议至少包含 3 条硬性否决规则。"
        )

    return count, warnings


def validate_criteria(
    text: str,
    reference_meta: ReferenceMeta,
    category_id: str = "",
) -> ValidationReport:
    """
    Validate generated criteria text against reference metadata.

    Runs truncation detection, required-section checks, schema field
    coverage, noise field detection, and veto clause counting.
    """
    report = ValidationReport()

    # Check 1 - Truncation detection
    reference_text = getattr(reference_meta, "reference_text", "") or ""
    report.truncation_detected = _detect_truncation(text, reference_text)
    if report.truncation_detected:
        report.warnings.append("生成文本可能被截断，长度不足或缺少完整结尾。")

    # Check 2 - Required sections
    hints = getattr(reference_meta, "generation_hints", None) or {}
    must_include = hints.get("must_include_sections", [])
    report.missing_sections = _check_required_sections(text, must_include)

    # Check 3 - Schema field mentions
    schema_fields = getattr(reference_meta, "schema_fields", None) or []
    report.missing_schema_fields, required_missing = _check_schema_fields(text, schema_fields)

    # Check 4 - Noise field detection
    report.noise_fields = _detect_noise_fields(text, category_id)
    if report.noise_fields:
        report.warnings.append(
            f"检测到不相关领域的字段: {', '.join(report.noise_fields)}"
        )

    # Check 5 - Veto clause count
    report.veto_clause_count, veto_warnings = _count_veto_clauses(text)
    report.warnings.extend(veto_warnings)

    # Determine overall validity
    report.is_valid = determine_overall_valid(report, required_missing)

    return report


def determine_overall_valid(report: ValidationReport, required_missing: list[str] | None = None) -> bool:
    """
    Determine if the report represents a valid result.

    Valid when: no truncation, no missing sections, no missing required
    schema fields. Noise fields and low veto counts are warnings only.
    """
    if report.truncation_detected:
        return False
    if report.missing_sections:
        return False

    # Only required schema fields block validity
    if required_missing:
        return False

    return True


def should_retry(report: ValidationReport) -> bool:
    """Return True if the generation should be retried."""
    return report.truncation_detected or len(report.missing_sections) > 0
