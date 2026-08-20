from concurrent.futures import ThreadPoolExecutor
from threading import get_ident

from stylemate.repositories.session import SessionWardrobeRepository


class ThreadBoundState(dict):
    def __init__(self):
        super().__init__()
        self.owner_thread = get_ident()

    def __getitem__(self, key):
        if get_ident() != self.owner_thread:
            raise KeyError(key)
        return super().__getitem__(key)


def test_session_repository_normalizes_partial_owner_bucket():
    state = {"owners": {"owner-1": {"profile": {"style_preference": "简约"}}}}
    repository = SessionWardrobeRepository(state)

    assert repository.get_profile("owner-1") == {"style_preference": "简约"}
    assert repository.list_garments("owner-1") == []
    assert repository.list_favorites("owner-1") == []
    assert state["owners"]["owner-1"] == {
        "garments": {},
        "profile": {"style_preference": "简约"},
        "favorites": {},
        "feedback": {},
    }


def test_session_repository_can_be_read_by_tool_worker_thread():
    state = ThreadBoundState()
    repository = SessionWardrobeRepository(state)

    with ThreadPoolExecutor(max_workers=1) as executor:
        garments = executor.submit(repository.list_garments, "owner-1").result()

    assert garments == []
    assert state["owners"]["owner-1"]["garments"] == {}
