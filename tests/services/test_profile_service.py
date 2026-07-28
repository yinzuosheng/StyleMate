from services.profile_service import ProfileService


def test_profile_merge_keeps_existing_value_and_reports_conflict(repo):
    service = ProfileService(repo)
    repo.save_profile("u1", {"style_preference": "简约"})

    merged, conflicts = service.merge(
        "u1", {"style_preference": "街头", "height": "171cm"}
    )

    assert merged == {"style_preference": "简约", "height": "171cm"}
    assert conflicts == ["style_preference"]


def test_profile_replace_allows_intentional_change_and_discards_unknown_keys(repo):
    service = ProfileService(repo)
    repo.save_profile("u1", {"style_preference": "简约"})

    profile = service.replace(
        "u1", {"style_preference": "街头", "unknown": "ignored"}
    )

    assert profile == {
        "height": "",
        "weight": "",
        "fit_preference": "",
        "style_preference": "街头",
        "color_preference": "",
        "scene_preference": "",
        "body_features": "",
    }
    assert service.get("u1") == profile
