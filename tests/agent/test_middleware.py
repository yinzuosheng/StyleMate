from unittest.mock import Mock

import requests
from pydantic import BaseModel, Field

from stylemate.agent.middleware import ToolContext, ToolExecutor
from stylemate.domain.models import Garment, ToolSpec
from stylemate.repositories.session import SessionWardrobeRepository


class SearchArguments(BaseModel):
    query: str = Field(min_length=1)


def tool_context(repo=None):
    return ToolContext(
        owner_id="owner-a",
        app_mode="demo",
        wardrobe_repository=repo or SessionWardrobeRepository({}),
        retriever=None,
        amap_client=None,
        settings=None,
    )


def test_network_tool_retries_once_then_returns_redacted_failure():
    call = Mock(side_effect=[requests.Timeout("secret sk-test"), {"ok": True}])

    result = ToolExecutor().execute(
        ToolSpec(name="get_weather", permission="read", timeout_seconds=2, retry_once=True),
        {},
        tool_context(),
        lambda _arguments, _context: call(),
    )

    assert call.call_count == 2
    assert result.status == "success"
    assert "sk-test" not in result.trace.summary


def test_inventory_validator_rejects_unknown_garment_ids(repo):
    result = ToolExecutor().execute(
        ToolSpec(
            name="recommend_inventory_outfit",
            permission="read",
            timeout_seconds=2,
            validates_inventory_ids=True,
        ),
        {},
        tool_context(repo=repo),
        lambda _arguments, _context: {"garment_ids": ["not-owned"]},
    )

    assert result.status == "failed"
    assert result.user_message == "推荐结果包含无效衣物，已停止展示。"


def test_trace_never_contains_full_document_or_api_key():
    result = ToolExecutor().execute(
        ToolSpec(name="rag_search", permission="read", timeout_seconds=2),
        {},
        tool_context(),
        lambda _arguments, _context: "A" * 5000 + " sk-secret",
    )

    assert len(result.trace.summary) <= 160
    assert "sk-secret" not in result.trace.summary


def test_arguments_are_validated_before_handler_is_called():
    call = Mock()
    result = ToolExecutor().execute(
        ToolSpec(
            name="rag_search",
            permission="read",
            timeout_seconds=2,
            arguments_model=SearchArguments,
        ),
        {"query": ""},
        tool_context(),
        lambda _arguments, _context: call(),
    )

    assert result.status == "failed"
    assert result.user_message == "输入参数无效，请检查后重试。"
    call.assert_not_called()


def test_inventory_validator_accepts_ids_owned_by_context_owner_only():
    repo = SessionWardrobeRepository({})
    garment = Garment(
        id="owner-a-top",
        name="top",
        category="上装",
        primary_color="black",
        seasons=["spring"],
        styles=["commute"],
        source="manual",
    )
    repo.save_garment("owner-a", garment)
    repo.save_garment("owner-b", garment.model_copy(update={"id": "owner-b-top"}))

    result = ToolExecutor().execute(
        ToolSpec(
            name="recommend_inventory_outfit",
            permission="read",
            timeout_seconds=2,
            validates_inventory_ids=True,
        ),
        {},
        tool_context(repo=repo),
        lambda _arguments, _context: {"recommendations": [{"garment_ids": ["owner-b-top"]}]},
    )

    assert result.status == "failed"
