"""Tests for src.services.reference_loader"""
import json
import pytest

from src.services.reference_loader import (
    SchemaField,
    ReferenceMeta,
    build_schema_section,
    calculate_max_output_tokens,
    estimate_tokens,
    load_category_index,
    load_reference_meta,
)


def test_load_category_index_returns_categories():
    index = load_category_index()
    assert "categories" in index
    assert len(index["categories"]) >= 3
    ids = [c["id"] for c in index["categories"]]
    assert "bicycle.road" in ids
    assert "digital.laptop" in ids
    assert "generic" in ids


def test_load_reference_meta_bicycle_road():
    meta = load_reference_meta("bicycle.road")
    assert meta.id == "bicycle.road"
    assert meta.version == "1.0"
    assert len(meta.schema_fields) == 12
    assert meta.features_db == "bicycle.road.features/"
    assert "核心分析原则" in meta.reference_text


def test_load_reference_meta_digital_laptop():
    meta = load_reference_meta("digital.laptop")
    assert meta.id == "digital.laptop"
    assert len(meta.schema_fields) == 8
    assert "model_chip" in [f.name for f in meta.schema_fields]


def test_load_reference_meta_generic():
    meta = load_reference_meta("generic")
    assert meta.id == "generic"


def test_load_reference_meta_unknown_raises():
    with pytest.raises(ValueError, match="Unknown category_id"):
        load_reference_meta("nonexistent.category")


def test_build_schema_section_bicycle():
    meta = load_reference_meta("bicycle.road")
    schema = build_schema_section(meta)
    assert "product_form" in schema
    assert "frameset" in schema
    assert "complete_bike" in schema
    assert "model_version" in schema
    assert "required" in schema
    # Check enum field shows values
    assert "[" in schema
    # Check object field shows structure
    assert "{status, comment, evidence}" in schema


def test_build_schema_section_digital():
    meta = load_reference_meta("digital.laptop")
    schema = build_schema_section(meta)
    assert "model_chip" in schema
    assert "battery_health" in schema


def test_estimate_tokens_non_negative():
    tokens = estimate_tokens("Hello world 你好世界")
    assert tokens > 0


def test_estimate_tokens_empty_string():
    tokens = estimate_tokens("")
    assert tokens >= 0


def test_calculate_max_output_tokens():
    meta = load_reference_meta("bicycle.road")
    index = load_category_index()
    cat = next(c for c in index["categories"] if c["id"] == "bicycle.road")
    result = calculate_max_output_tokens(meta, cat)
    assert result >= 1500
    assert result <= 8000


def test_calculate_max_output_tokens_respects_minimum():
    meta = ReferenceMeta(
        id="test", version="1", schema_fields=[], generation_hints={},
        reference_text="short",
    )
    result = calculate_max_output_tokens(meta, {"max_output_tokens": 3000})
    assert result == 3000


def test_calculate_max_output_tokens_caps_at_8000():
    meta = ReferenceMeta(
        id="test", version="1", schema_fields=[], generation_hints={},
        reference_text="x" * 20000,
    )
    result = calculate_max_output_tokens(meta, {"max_output_tokens": 50000})
    assert result == 8000
