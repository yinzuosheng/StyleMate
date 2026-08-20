from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from threading import get_ident

import pytest

from stylemate.domain.models import (
    ConversationFacts,
    ConversationMessage,
    ConversationState,
    PendingAction,
    UserDocument,
)
from stylemate.repositories.agent_session import SessionAgentRepository
from stylemate.repositories.agent_sqlite import SQLiteAgentRepository


@pytest.fixture(params=["session", "sqlite"])
def repo(request, tmp_path: Path):
    if request.param == "session":
        return SessionAgentRepository({})
    return SQLiteAgentRepository(tmp_path / "agent.db")


def conversation(owner_id: str = "owner-a", conversation_id: str = "thread-1") -> ConversationState:
    return ConversationState(
        owner_id=owner_id,
        conversation_id=conversation_id,
        messages=[ConversationMessage(role="user", content="杭州天气")],
        facts=ConversationFacts(topics=["weather"], locations=["杭州"]),
    )


def pending(*, expires_at: datetime) -> PendingAction:
    return PendingAction(
        id="action-1",
        owner_id="owner-a",
        conversation_id="thread-1",
        operation="delete",
        target_garment_id="g-1",
        created_at=expires_at - timedelta(minutes=10),
        expires_at=expires_at,
    )


def document() -> UserDocument:
    return UserDocument(
        owner_id="owner-a",
        conversation_id="thread-1",
        document_id="doc-1",
        filename="care.md",
        mime_type="text/markdown",
        text="羊毛洗护说明",
        created_at=datetime(2026, 8, 13, 12, 0, 0),
    )


def test_conversation_pending_and_documents_are_owner_isolated(repo):
    saved_conversation = conversation()
    saved_pending = pending(expires_at=datetime.now() + timedelta(minutes=10))
    saved_document = document()

    repo.save_conversation(saved_conversation)
    repo.save_pending(saved_pending)
    repo.save_document(saved_document)

    assert repo.load_conversation("owner-a", "thread-1") == saved_conversation
    assert repo.get_pending("owner-a", "thread-1") == saved_pending
    assert repo.list_documents("owner-a", "thread-1") == [saved_document]
    assert repo.load_conversation("owner-b", "thread-1").messages == []
    assert repo.get_pending("owner-b", "thread-1") is None
    assert repo.list_documents("owner-b", "thread-1") == []


def test_clear_methods_only_remove_the_target_owner_conversation(repo):
    repo.save_conversation(conversation())
    repo.save_conversation(conversation("owner-b"))
    repo.save_pending(pending(expires_at=datetime.now() + timedelta(minutes=10)))
    repo.save_pending(
        PendingAction(
            id="action-2",
            owner_id="owner-b",
            conversation_id="thread-1",
            operation="add",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(minutes=10),
        )
    )

    repo.clear_conversation("owner-a", "thread-1")
    repo.clear_pending("owner-a", "thread-1")

    assert repo.load_conversation("owner-a", "thread-1").messages == []
    assert repo.get_pending("owner-a", "thread-1") is None
    assert repo.load_conversation("owner-b", "thread-1").messages[0].content == "杭州天气"
    assert repo.get_pending("owner-b", "thread-1").id == "action-2"


def test_expired_pending_action_is_not_returned(repo):
    repo.save_pending(pending(expires_at=datetime.now() - timedelta(seconds=1)))

    assert repo.get_pending("owner-a", "thread-1") is None


def test_sqlite_restores_agent_data_through_a_fresh_instance(tmp_path: Path):
    database_path = tmp_path / "agent.db"
    original = SQLiteAgentRepository(database_path)
    saved_conversation = conversation()
    saved_pending = pending(expires_at=datetime.now() + timedelta(minutes=10))
    saved_document = document()
    original.save_conversation(saved_conversation)
    original.save_pending(saved_pending)
    original.save_document(saved_document)

    restored = SQLiteAgentRepository(database_path)

    assert restored.load_conversation("owner-a", "thread-1") == saved_conversation
    assert restored.get_pending("owner-a", "thread-1") == saved_pending
    assert restored.list_documents("owner-a", "thread-1") == [saved_document]


def test_document_delete_and_clear_are_owner_conversation_scoped(repo):
    first = document()
    second = first.model_copy(
        update={"conversation_id": "thread-2", "document_id": "doc-2"}
    )
    other_owner = first.model_copy(
        update={"owner_id": "owner-b", "document_id": "doc-3"}
    )
    for item in (first, second, other_owner):
        repo.save_document(item)

    repo.delete_document("owner-a", "thread-1", "doc-1")

    assert repo.list_documents("owner-a", "thread-1") == []
    assert repo.list_documents("owner-a", "thread-2") == [second]
    assert repo.list_documents("owner-b", "thread-1") == [other_owner]

    repo.clear_documents("owner-a", "thread-2")

    assert repo.list_documents("owner-a", "thread-2") == []
    assert repo.list_documents("owner-b", "thread-1") == [other_owner]


def test_session_agent_repository_can_be_read_by_tool_worker_thread():
    class ThreadBoundState(dict):
        def __init__(self):
            super().__init__()
            self.owner_thread = get_ident()

        def __getitem__(self, key):
            if get_ident() != self.owner_thread:
                raise KeyError(key)
            return super().__getitem__(key)

    state = ThreadBoundState()
    repository = SessionAgentRepository(state)

    with ThreadPoolExecutor(max_workers=1) as executor:
        saved = executor.submit(
            repository.load_conversation, "owner-a", "thread-1"
        ).result()

    assert saved.messages == []
    assert state["stylemate_agent"]["owner-a"]["conversations"] == {}


def test_conversation_index_lists_recent_owner_sessions_with_titles(repo):
    older = conversation("owner-a", "thread-old").model_copy(
        update={
            "messages": [
                ConversationMessage(
                    role="user",
                    content="周末去杭州旅行",
                    created_at=datetime(2026, 8, 17, 9, 0, 0),
                )
            ]
        }
    )
    newer = conversation("owner-a", "thread-new").model_copy(
        update={
            "messages": [
                ConversationMessage(
                    role="user",
                    content="今天通勤穿什么",
                    created_at=datetime(2026, 8, 18, 9, 0, 0),
                ),
                ConversationMessage(
                    role="assistant",
                    content="建议轻薄通勤搭配。",
                    created_at=datetime(2026, 8, 18, 9, 1, 0),
                ),
            ]
        }
    )
    repo.save_conversation(older)
    repo.save_conversation(newer)
    repo.save_conversation(conversation("owner-b", "other"))

    sessions = repo.list_conversations("owner-a")

    assert [item["conversation_id"] for item in sessions] == [
        "thread-new",
        "thread-old",
    ]
    assert sessions[0]["title"] == "今天通勤穿什么"
    assert sessions[0]["message_count"] == 2
