"""State and bounded model context for the StyleMate two-node graph."""

from __future__ import annotations

import json
import operator
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph.message import add_messages

from stylemate.agent.memory import migrate_legacy_summary, prune_expired_facts
from stylemate.domain.models import ConversationFacts


class AgentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    conversation_facts: dict[str, Any]
    owner_id: str
    conversation_id: str
    app_mode: str
    profile: dict[str, str]
    traces: Annotated[list[dict[str, Any]], operator.add]
    sources: Annotated[list[dict[str, str]], operator.add]
    pending_action: dict[str, Any] | None
    retry_count: int
    wardrobe_context_refs: list[str]
    model_calls: Annotated[int, operator.add]
    tool_calls: Annotated[int, operator.add]


def initial_state(text: str, *, owner_id: str = "", conversation_id: str = "", facts: ConversationFacts | dict[str, Any] | None = None, summary: str = "", app_mode: str = "demo", profile: dict[str, str] | None = None, messages: list[BaseMessage] | None = None) -> AgentState:
    """Make a fresh turn state; persisted history is supplied separately by the service."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("消息不能为空")
    conversation_facts = prune_expired_facts(
        migrate_legacy_summary(ConversationFacts.model_validate(facts or {}), summary)
    )
    return {
        "messages": [*(messages or []), HumanMessage(content=text.strip())],
        "conversation_facts": conversation_facts.model_dump(exclude_defaults=True),
        "owner_id": owner_id,
        "conversation_id": conversation_id,
        "app_mode": app_mode,
        "profile": dict(profile or {}),
        "traces": [],
        "sources": [],
        "pending_action": None,
        "retry_count": 0,
        "wardrobe_context_refs": [],
        "model_calls": 0,
        "tool_calls": 0,
    }


def model_messages(state: AgentState, system_prompt: str) -> list[BaseMessage]:
    """Expose only system, structured facts and the recent human/AI dialogue.

    Tool payloads from earlier turns are deliberately never reintroduced.
    """
    context: list[BaseMessage] = [SystemMessage(content=system_prompt)]
    facts = ConversationFacts.model_validate(state.get("conversation_facts") or {})
    rendered_facts = facts.model_dump(
        exclude={"provenance"}, exclude_defaults=True
    )
    if rendered_facts:
        context.append(
            SystemMessage(
                content="结构化会话事实（仅供延续当前会话）："
                + json.dumps(rendered_facts, ensure_ascii=False, separators=(",", ":"))
            )
        )
    profile = {
        key: value
        for key, value in state.get("profile", {}).items()
        if isinstance(value, str) and value.strip()
    }
    if profile:
        rendered = "；".join(f"{key}={value}" for key, value in sorted(profile.items()))
        context.append(SystemMessage(content=f"用户已确认的长期偏好：{rendered}"))
    dialogue = [message for message in state.get("messages", []) if isinstance(message, (HumanMessage, AIMessage))]
    context.extend(dialogue[-8:])
    # Tool messages belong to the active graph loop only, never to persisted history.
    context.extend(message for message in state.get("messages", []) if getattr(message, "type", "") == "tool")
    return context

