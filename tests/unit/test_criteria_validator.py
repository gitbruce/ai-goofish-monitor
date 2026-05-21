"""Tests for src.services.criteria_validator"""
import pytest

from src.services.criteria_validator import (
    ValidationReport,
    determine_overall_valid,
    should_retry,
    validate_criteria,
)
from src.services.reference_loader import ReferenceMeta, SchemaField


def _make_meta(
    sections=None,
    fields=None,
    reference_text="x" * 200,
):
    if sections is None:
        sections = ["第一部分：核心分析原则", "第二部分：详细分析指南"]
    if fields is None:
        fields = [
            SchemaField(name="product_condition", type="object", required=True),
            SchemaField(name="seller_type", type="object", required=True),
        ]
    return ReferenceMeta(
        id="test",
        version="1",
        schema_fields=fields,
        generation_hints={"must_include_sections": sections},
        reference_text=reference_text,
    )


def test_validate_criteria_all_checks_pass():
    meta = _make_meta()
    text = (
        "第一部分：核心分析原则\n"
        "第二部分：详细分析指南\n"
        "product_condition 和 seller_type 字段分析。\n"
        "一票否决硬性原则：\n"
        "- **条件1**：必须满足\n"
        "- **条件2**：必须满足\n"
        "- **条件3**：必须满足\n"
        "这是一段完整文本。"
    )
    report = validate_criteria(text, meta, "test")
    assert report.is_valid is True
    assert report.truncation_detected is False
    assert report.missing_sections == []
    assert report.missing_schema_fields == []


def test_validate_criteria_truncation_detected():
    meta = _make_meta(reference_text="x" * 2000)
    text = "非常短的文本"
    report = validate_criteria(text, meta, "test")
    assert report.truncation_detected is True
    assert report.is_valid is False


def test_validate_criteria_missing_sections():
    meta = _make_meta(sections=["第一部分：A", "第二部分：B"])
    text = "第一部分：A\n完整文本。"
    report = validate_criteria(text, meta, "test")
    assert "第二部分：B" in report.missing_sections
    assert report.is_valid is False


def test_validate_criteria_missing_schema_fields():
    meta = _make_meta(fields=[
        SchemaField(name="field_a", type="object", required=True),
        SchemaField(name="field_b", type="object", required=True),
    ])
    text = "field_a 分析。\n完整文本结尾。"
    report = validate_criteria(text, meta, "test")
    assert "field_b" in report.missing_schema_fields


def test_validate_criteria_noise_fields_bicycle_category():
    meta = _make_meta()
    text = "包含 battery_health 和 model_chip 的文本。完整结尾。"
    report = validate_criteria(text, meta, "bicycle.road")
    assert "battery_health" in report.noise_fields
    assert "model_chip" in report.noise_fields


def test_validate_criteria_noise_fields_digital_category():
    meta = _make_meta()
    text = "包含 groupset 和 frame_size_fit 的文本。完整结尾。"
    report = validate_criteria(text, meta, "digital.laptop")
    assert "groupset" in report.noise_fields
    assert "frame_size_fit" in report.noise_fields


def test_validate_criteria_veto_clause_count():
    meta = _make_meta()
    text = (
        "一票否决硬性原则：\n"
        "- **条件1**：必须满足\n"
        "- **条件2**：必须满足\n"
        "完整文本结尾。"
    )
    report = validate_criteria(text, meta, "test")
    assert report.veto_clause_count == 2
    assert any("偏少" in w for w in report.warnings)


def test_validate_criteria_veto_section_missing():
    meta = _make_meta()
    text = "没有否决条款的文本。完整结尾。"
    report = validate_criteria(text, meta, "test")
    assert report.veto_clause_count == 0


def test_should_retry_on_truncation():
    report = ValidationReport(truncation_detected=True, missing_sections=[])
    assert should_retry(report) is True


def test_should_retry_on_missing_sections():
    report = ValidationReport(
        truncation_detected=False,
        missing_sections=["第一部分"],
    )
    assert should_retry(report) is True


def test_should_retry_false_when_valid():
    report = ValidationReport(
        truncation_detected=False,
        missing_sections=[],
    )
    assert should_retry(report) is False


def test_determine_overall_valid_with_required_missing():
    report = ValidationReport(
        truncation_detected=False,
        missing_sections=[],
    )
    assert determine_overall_valid(report, ["required_field"]) is False


def test_determine_overall_valid_all_clear():
    report = ValidationReport(
        truncation_detected=False,
        missing_sections=[],
    )
    assert determine_overall_valid(report, []) is True
