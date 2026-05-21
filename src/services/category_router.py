"""
品类路由服务
根据用户描述，通过 AI 将需求路由到最匹配的品类
"""
import json
import os
from typing import List, Optional

from pydantic import BaseModel, Field

from src.services.reference_loader import load_category_index
from src.infrastructure.external.ai_client import AIClient


class RouteRequest(BaseModel):
    """路由请求"""

    user_description: str
    index_summaries: List[dict]


class RouteResponse(BaseModel):
    """路由响应"""

    category: str
    confidence: float
    reasoning: str


_INDEX_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "prompts",
    "references",
    "_index.json",
)


def build_index_summaries(index_data: dict) -> list[dict]:
    """从 _index.json 提取每个品类的 id 和摘要"""
    categories = index_data.get("categories", [])
    return [
        {"id": cat.get("id", ""), "summary": cat.get("summary", "")}
        for cat in categories
    ]


def build_router_prompt(request: RouteRequest) -> str:
    """构建品类路由 prompt"""
    lines = [
        f"  {item['id']}: {item['summary']}"
        for item in request.index_summaries
    ]
    formatted = "\n".join(lines)
    return (
        "你是品类路由器。下面是可选品类清单，每项含1行摘要：\n"
        f"{formatted}\n\n"
        f"用户需求：{request.user_description}\n\n"
        '请只输出JSON：\n'
        '{"category": "<必须在清单id内,不能编造>", '
        '"confidence": 0.0-1.0, '
        '"reasoning": "<不超过20字>"}\n'
        '若无法归入任何品类，category返回"generic"。'
    )


def _load_index_fallback() -> dict:
    """当 reference_loader 不可用时的兜底加载"""
    try:
        with open(_INDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"categories": []}


async def route_category(
    user_description: str,
    ai_client: Optional[AIClient] = None,
) -> RouteResponse:
    """
    根据用户描述路由到对应品类。

    Args:
        user_description: 用户的监控需求描述
        ai_client: 可选的 AI 客户端实例，不提供则自动创建

    Returns:
        RouteResponse 包含 category / confidence / reasoning
    """
    generic_fallback = RouteResponse(
        category="generic", confidence=0.0, reasoning="AI不可用"
    )

    # 加载品类索引
    try:
        index_data = load_category_index()
    except Exception:
        index_data = _load_index_fallback()

    summaries = build_index_summaries(index_data)
    if not summaries:
        return RouteResponse(
            category="generic", confidence=0.0, reasoning="品类索引为空"
        )

    valid_ids = {s["id"] for s in summaries}

    # 准备 AI 客户端
    owns_client = ai_client is None
    if ai_client is None:
        try:
            ai_client = AIClient()
        except Exception:
            return generic_fallback

    if not ai_client.is_available():
        if owns_client:
            await ai_client.close()
        return generic_fallback

    try:
        request = RouteRequest(
            user_description=user_description,
            index_summaries=summaries,
        )
        prompt = build_router_prompt(request)
        messages = [{"role": "user", "content": prompt}]

        response_text = await ai_client._call_ai(
            messages,
            temperature=0.0,
            max_output_tokens=200,
            enable_json_output=True,
        )

        # 解析 JSON 响应
        try:
            parsed = json.loads(response_text)
        except (json.JSONDecodeError, TypeError):
            return RouteResponse(
                category="generic", confidence=0.0, reasoning="AI响应解析失败"
            )

        category = str(parsed.get("category", "generic")).strip()
        confidence = float(parsed.get("confidence", 0.0))
        reasoning = str(parsed.get("reasoning", ""))[:20]

        # 校验 category 是否在索引中
        if category not in valid_ids:
            category = "generic"
            confidence = min(confidence, 0.3)

        # 低置信度回退
        if confidence < 0.6:
            category = "generic"

        return RouteResponse(
            category=category,
            confidence=confidence,
            reasoning=reasoning,
        )

    except Exception as e:
        print(f"品类路由失败: {e}")
        return RouteResponse(
            category="generic", confidence=0.0, reasoning="路由异常"
        )
    finally:
        if owns_client:
            await ai_client.close()
