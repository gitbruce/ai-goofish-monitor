"""Tests for src.services.category_router"""
import pytest

from src.services.category_router import (
    RouteRequest,
    RouteResponse,
    build_index_summaries,
    build_router_prompt,
)


def test_build_index_summaries():
    index_data = {
        "categories": [
            {"id": "bicycle.road", "summary": "公路自行车", "keywords_hint": ["SL8"]},
            {"id": "digital.laptop", "summary": "笔记本", "keywords_hint": ["MacBook"]},
            {"id": "generic", "summary": "通用"},
        ]
    }
    summaries = build_index_summaries(index_data)
    assert len(summaries) == 3
    assert summaries[0] == {"id": "bicycle.road", "summary": "公路自行车"}
    assert summaries[2] == {"id": "generic", "summary": "通用"}


def test_build_index_summaries_empty():
    summaries = build_index_summaries({"categories": []})
    assert summaries == []


def test_build_router_prompt():
    request = RouteRequest(
        user_description="我想买一辆闪电SL8公路车",
        index_summaries=[
            {"id": "bicycle.road", "summary": "公路自行车"},
            {"id": "generic", "summary": "通用"},
        ],
    )
    prompt = build_router_prompt(request)
    assert "闪电SL8公路车" in prompt
    assert "bicycle.road" in prompt
    assert "generic" in prompt
    assert "品类路由器" in prompt


def test_route_response_model():
    resp = RouteResponse(category="bicycle.road", confidence=0.9, reasoning="公路车需求")
    assert resp.category == "bicycle.road"
    assert resp.confidence == 0.9


def test_route_request_model():
    req = RouteRequest(
        user_description="test",
        index_summaries=[{"id": "test", "summary": "test"}],
    )
    assert req.user_description == "test"
