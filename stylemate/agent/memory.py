"""Deterministic, bounded extraction for session-scoped conversation facts."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from stylemate.domain.models import ConversationFacts, ConversationMessage, FactProvenance

_TOPIC_KEYWORDS = {
    "outfit": ("搭配", "穿什么", "穿搭"),
    "weather": ("天气", "温度", "下雨"),
    "wardrobe": ("衣橱", "衣柜", "库存", "衣物"),
    "size": ("尺码", "身高", "体重"),
    "care": ("洗护", "护理", "清洗", "保养"),
    "knowledge": ("知识库", "资料", "文档"),
    "wardrobe_write": ("新增", "修改", "删除"),
}
_SCENES = ("面试", "通勤", "约会", "日常", "旅行", "旅游", "运动", "聚会", "婚礼")
_SCENE_ALIASES = {"旅游": "旅行"}
_CONSTRAINTS = (
    "不紧身",
    "不要紧身",
    "宽松",
    "修身",
    "正式",
    "休闲",
    "保暖",
    "防雨",
    "轻便",
    "不穿裙子",
    "不要高跟鞋",
)
_LOCATION_PATTERNS = (
    re.compile(r"(?:改成|换成)\s*([\u4e00-\u9fff]{2,6})(?:市)?(?=面试|出差|旅行|旅游|通勤|天气)"),
    re.compile(r"(?:去|到|在)\s*([\u4e00-\u9fff]{2,6})(?:市)?(?=面试|出差|旅行|旅游|天气)"),
    re.compile(r"([\u4e00-\u9fff]{2,6})(?:市)?天气"),
)
_GARMENT_ID_PATTERN = re.compile(
    r"(?:(?:衣物\s*)?(?:id|编号)\s*[:：]?\s*|衣物\s*[:：]\s*)([\w-]+)",
    re.I,
)
_CORRECTION_MARKERS = ("改成", "换成", "不是", "不去", "更正")
_TEMPORARY_FACT_TTL = timedelta(hours=24)


def migrate_legacy_summary(facts: ConversationFacts, summary: str) -> ConversationFacts:
    """Preserve an old free-text summary once without continuing that format."""
    note = summary.strip()[-500:]
    if not note:
        return facts
    return facts.model_copy(
        update={"legacy_notes": _bounded(facts.legacy_notes, [note], 2)}
    )


def update_conversation_facts(
    facts: ConversationFacts,
    message: ConversationMessage,
    *,
    now: datetime | None = None,
) -> ConversationFacts:
    """Merge typed facts immediately and retain auditable source metadata."""
    current_time = now or message.created_at
    facts = prune_expired_facts(facts, current_time)
    if message.role != "user":
        return facts
    text = " ".join(message.content.split())
    topics = [
        topic
        for topic, keywords in _TOPIC_KEYWORDS.items()
        if any(keyword in text for keyword in keywords)
    ]
    scenes = [_SCENE_ALIASES.get(scene, scene) for scene in _SCENES if scene in text]
    locations = [
        match.group(1)
        for pattern in _LOCATION_PATTERNS
        if (match := pattern.search(text)) is not None
    ]
    constraints = list(
        dict.fromkeys(constraint for constraint in _CONSTRAINTS if constraint in text)
    )
    correction = any(marker in text for marker in _CORRECTION_MARKERS)
    values_by_field = {
        "topics": topics,
        "scenes": scenes,
        "locations": locations,
        "garment_ids": _GARMENT_ID_PATTERN.findall(text),
        "constraints": constraints,
    }
    limits = {
        "topics": 12,
        "scenes": 8,
        "locations": 8,
        "garment_ids": 16,
        "constraints": 12,
    }
    updates: dict[str, object] = {"last_user_goal": text[:400]}
    provenance = list(facts.provenance)
    for field, additions in values_by_field.items():
        existing = list(getattr(facts, field))
        replace = correction and field in {"scenes", "locations"} and additions
        if replace:
            existing = []
            provenance = [item for item in provenance if item.field != field]
        if field == "constraints":
            existing = _remove_constraint_conflicts(existing, additions)
        active = _bounded(existing, additions, limits[field])
        updates[field] = active
        provenance = _record_provenance(
            provenance,
            field,
            additions,
            message,
            current_time,
            _TEMPORARY_FACT_TTL if field == "constraints" else None,
        )
        provenance = [
            item
            for item in provenance
            if item.field != field or item.value in active
        ]
    provenance = _record_provenance(
        [item for item in provenance if item.field != "last_user_goal"],
        "last_user_goal",
        [text[:400]],
        message,
        current_time,
        None,
    )
    updates["provenance"] = provenance[-80:]
    return facts.model_copy(update=updates)


def prune_expired_facts(
    facts: ConversationFacts, now: datetime | None = None
) -> ConversationFacts:
    current_time = now or datetime.now()
    expired = {
        (item.field, item.value)
        for item in facts.provenance
        if item.expires_at is not None
        and _comparable_time(current_time, item.expires_at) >= item.expires_at
    }
    if not expired:
        return facts
    updates: dict[str, object] = {
        "provenance": [
            item
            for item in facts.provenance
            if (item.field, item.value) not in expired
        ]
    }
    for field in ("topics", "scenes", "locations", "garment_ids", "constraints"):
        updates[field] = [
            value for value in getattr(facts, field) if (field, value) not in expired
        ]
    return facts.model_copy(update=updates)


def _record_provenance(
    existing: list[FactProvenance],
    field: str,
    values: list[str],
    message: ConversationMessage,
    updated_at: datetime,
    ttl: timedelta | None,
) -> list[FactProvenance]:
    result = list(existing)
    for value in values:
        if not value:
            continue
        result = [
            item
            for item in result
            if not (item.field == field and item.value == value)
        ]
        result.append(
            FactProvenance(
                field=field,
                value=value,
                source_message_id=message.id,
                updated_at=updated_at,
                expires_at=updated_at + ttl if ttl else None,
            )
        )
    return result


def _remove_constraint_conflicts(
    existing: list[str], additions: list[str]
) -> list[str]:
    conflicts = {
        "修身": {"宽松", "不紧身", "不要紧身"},
        "宽松": {"修身"},
        "不紧身": {"修身"},
        "不要紧身": {"修身"},
    }
    blocked = set().union(*(conflicts.get(value, set()) for value in additions))
    return [value for value in existing if value not in blocked]


def _comparable_time(value: datetime, reference: datetime) -> datetime:
    if value.tzinfo is None and reference.tzinfo is not None:
        return value.replace(tzinfo=reference.tzinfo)
    if value.tzinfo is not None and reference.tzinfo is None:
        return value.replace(tzinfo=None)
    return value


def _bounded(existing: list[str], additions: list[str], limit: int) -> list[str]:
    values = [value.strip() for value in existing if isinstance(value, str) and value.strip()]
    for value in additions:
        normalized = value.strip()
        if not normalized:
            continue
        if normalized in values:
            values.remove(normalized)
        values.append(normalized)
    return values[-limit:]


__all__ = [
    "migrate_legacy_summary",
    "prune_expired_facts",
    "update_conversation_facts",
]

