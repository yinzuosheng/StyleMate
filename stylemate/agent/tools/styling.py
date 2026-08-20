"""Read-only location, size, and retrieval-backed styling tools."""

from __future__ import annotations

from typing import Any

import requests

from stylemate.agent.middleware import ToolContext
from stylemate.agent.tool_schemas import (
    CareArguments,
    OpenOutfitArguments,
    PurchaseArguments,
    RagSearchArguments,
    SizeArguments,
    TravelArguments,
    WeatherArguments,
)
from stylemate.skills.knowledge_qa import KnowledgeQASkill, KnowledgeQuery


def get_user_location(arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    """Delegate location lookup exclusively to the configured AmapClient."""
    del arguments
    if context.amap_client is None:
        return {"available": False, "reason": "location_service_unavailable"}
    result = context.amap_client.locate()
    _raise_retryable_amap_result(result)
    return {
        "available": result.available,
        "city": result.city,
        "province": result.province,
        "adcode": result.adcode,
        "reason": result.reason,
    }


def get_weather(arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    """Delegate weather lookup exclusively to the configured AmapClient."""
    city = WeatherArguments.model_validate(arguments).city
    if context.amap_client is None:
        return {"available": False, "reason": "weather_service_unavailable"}
    result = context.amap_client.weather(city)
    _raise_retryable_amap_result(result)
    return {
        "available": result.available,
        "city": result.city,
        "summary": result.summary,
        "temperature_c": result.temperature_c,
        "humidity": result.humidity,
        "reason": result.reason,
    }


def recommend_size(arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    """Return a bounded size reference, never a universal brand-size claim."""
    del context
    values = SizeArguments.model_validate(arguments)
    size = _size_for(values.height_cm, values.weight_kg)
    size = _shift_size(size, values.fit_preference)
    return {
        "recommended_size": size,
        "height_cm": values.height_cm,
        "weight_kg": values.weight_kg,
        "fit_preference": values.fit_preference,
        "reference_note": "尺码建议仅供参考，请以具体品牌的尺码表和试穿感受为准。",
    }


def care_guide(arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    """Find care guidance through RAG and retain each source citation."""
    material = CareArguments.model_validate(arguments).material
    return _rag_result(f"{material} 衣物洗护注意事项", context)


def rag_search(arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    """Search the retrieval corpus in the caller's owner/conversation scope."""
    query = RagSearchArguments.model_validate(arguments).query
    return _rag_result(query, context)


def recommend_open_outfit(
    arguments: dict[str, Any], context: ToolContext
) -> dict[str, Any]:
    """Generate a knowledge-first outfit plan that does not require inventory."""
    values = OpenOutfitArguments.model_validate(arguments)
    temperature = values.temperature_c
    if temperature is None:
        temperature = 24.0
    scene = values.scene or "日常"
    if temperature >= 28:
        top, bottom, shoes = "透气短袖或亚麻衬衫", "轻薄长裤或五分裤", "透气运动鞋或凉鞋"
        avoid = "厚外套、厚针织和不透气面料"
    elif temperature <= 12:
        top, bottom, shoes = "保暖内层+针织衫", "厚长裤", "短靴或防滑运动鞋"
        avoid = "单层薄款上装和露踝鞋履"
    else:
        top, bottom, shoes = "长袖衬衫或薄针织", "直筒长裤", "休闲鞋或乐福鞋"
        avoid = "过多厚重层次"
    if "通勤" in scene:
        color = "白、藏蓝、灰、卡其等低饱和色"
    elif "约会" in scene:
        color = "米白、浅蓝或低饱和暖色"
    else:
        color = "白、浅蓝、灰绿等清爽配色"
    knowledge = _rag_result(
        f"{scene} {values.weather_condition or ''} {temperature:g}度 穿搭建议",
        context,
    )
    return {
        "recommendation": (
            "通用穿搭建议：\n"
            f"- 上装：{top}\n"
            f"- 下装：{bottom}\n"
            f"- 鞋履：{shoes}\n"
            f"- 配色：{color}\n"
            f"- 注意：避免{avoid}。"
        ),
        "alternatives": [
            "如果不想上传衣物，可按以上类别选择已有同类单品。",
            "出门前根据体感温度调整一层，优先选择透气、易活动的面料。",
        ],
        "sources": knowledge.get("sources", []),
    }


def recommend_purchases(
    arguments: dict[str, Any], context: ToolContext
) -> dict[str, Any]:
    """Suggest purchase priorities from season/weather and current category gaps."""
    values = PurchaseArguments.model_validate(arguments)
    temperature = values.temperature_c if values.temperature_c is not None else 24.0
    season = values.season or _season_for_temperature(temperature)
    owned = context.wardrobe_repository.list_garments(context.owner_id)
    categories = {garment.category for garment in owned}
    basics = _purchase_basics(season, temperature)
    missing = [item for item in basics if item["category"] not in categories]
    priorities = missing or basics[:2]
    knowledge = _rag_result(
        f"{season}季 {values.scene} 衣橱基础单品 购买建议",
        context,
    )
    return {
        "season": season,
        "priorities": priorities[:4],
        "message": "优先购买：" + "、".join(item["item"] for item in priorities[:4]),
        "sources": knowledge.get("sources", []),
    }


def travel_packing(arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    """Create a weather- and activity-aware packing list without requiring inventory."""
    values = TravelArguments.model_validate(arguments)
    activities = values.activities or ["城市观光"]
    weather_summary = ""
    if values.weather_condition:
        weather_summary = values.weather_condition
        if values.temperature_c is not None:
            weather_summary += f"，{values.temperature_c:g}°C"
    packing = [
        f"上衣 {min(values.days + 1, 4)} 件（按{weather_summary or '目的地天气'}准备）",
        f"下装 {min(max(2, values.days), 4)} 条",
        "舒适步行鞋 1 双，必要时增加备用鞋",
        "轻薄外套 1 件，应对早晚温差和室内空调",
        "充电器、证件和常用洗护用品",
    ]
    if values.temperature_c is not None and values.temperature_c <= 12:
        packing.extend(["保暖内层 1 件", "围巾或帽子 1 件"])
    elif values.temperature_c is not None and values.temperature_c >= 28:
        packing.extend(["防晒用品", "透气替换上衣 1 件"])
    if any(keyword in (values.weather_condition or "") for keyword in ("雨", "阵雨", "雷")):
        packing.append("轻量雨具或防水收纳袋")
    if any("户外" in activity for activity in activities):
        packing.extend(["防晒用品", "轻量雨具或防水收纳袋"])
    return {
        "destination": values.destination,
        "days": values.days,
        "activities": activities,
        "packing_list": packing,
        "message": f"{values.destination}{values.days}天行程行李清单：",
        "weather_summary": weather_summary,
        "sources": [],
    }


def _season_for_temperature(temperature: float) -> str:
    if temperature >= 28:
        return "夏"
    if temperature <= 12:
        return "冬"
    return "春秋"


def _purchase_basics(season: str, temperature: float) -> list[dict[str, str]]:
    if season == "夏" or temperature >= 28:
        return [
            {"item": "透气短袖或亚麻衬衫", "category": "上装", "reason": "应对高温并减少闷热"},
            {"item": "轻薄长裤或五分裤", "category": "下装", "reason": "保持活动度和透气性"},
            {"item": "透气运动鞋或凉鞋", "category": "鞋履", "reason": "适合日常步行"},
        ]
    if season == "冬" or temperature <= 12:
        return [
            {"item": "保暖内层", "category": "上装", "reason": "提高核心保暖"},
            {"item": "羽绒服或保暖外套", "category": "外套", "reason": "应对低温和风寒"},
            {"item": "防滑短靴", "category": "鞋履", "reason": "兼顾保暖与通勤"},
        ]
    return [
        {"item": "薄外套或风衣", "category": "外套", "reason": "应对昼夜温差"},
        {"item": "长袖衬衫或薄针织", "category": "上装", "reason": "适合分层穿着"},
        {"item": "直筒长裤", "category": "下装", "reason": "覆盖通勤和日常场景"},
    ]


def _raise_retryable_amap_result(result: Any) -> None:
    """Turn safe typed transient failures back into executor-retryable errors."""
    if getattr(result, "available", False):
        return
    reason = getattr(result, "reason", "")
    if reason == "timeout":
        raise requests.Timeout("amap request timed out")
    if reason == "upstream_error":
        raise requests.ConnectionError("amap service unavailable")


def _rag_result(query: str, context: ToolContext) -> dict[str, Any]:
    configured_top_k = getattr(context.settings, "rag_top_k", 4)
    top_k = min(6, max(1, int(configured_top_k)))
    outcome = KnowledgeQASkill(context.retriever).run(
        context.owner_id,
        context.conversation_id,
        KnowledgeQuery(query=query, top_k=top_k),
    )
    return {
        **outcome.data,
        "skill_trace": outcome.trace.model_dump(mode="json"),
    }


def _size_for(height_cm: float, weight_kg: float) -> str:
    rules = [
        (165, 47.5, "S"),
        (170, 57.5, "M"),
        (175, 67.5, "L"),
        (178, 75, "XL"),
        (182, 82.5, "2XL"),
        (185, 90, "3XL"),
        (190, 105, "4XL"),
    ]
    for max_height, max_weight, size in rules:
        if height_cm <= max_height and weight_kg <= max_weight:
            return size
    return "5XL"


def _shift_size(size: str, preference: str) -> str:
    sizes = ["S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL"]
    index = sizes.index(size)
    if any(word in preference for word in ("宽松", "偏松")):
        index += 1
    elif any(word in preference for word in ("修身", "偏紧")):
        index -= 1
    return sizes[max(0, min(index, len(sizes) - 1))]
