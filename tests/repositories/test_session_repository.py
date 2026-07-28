from repositories.session import SessionWardrobeRepository


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
