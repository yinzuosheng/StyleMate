from domain.models import OutfitRequest
from skills.outfit_planning import OutfitPlanningSkill


def test_skill_returns_recommendations_from_owner_inventory(repo, sample_garments):
    for garment in sample_garments:
        repo.save_garment("u1", garment)

    outcome = OutfitPlanningSkill(repo).run("u1", OutfitRequest(scene="\u901a\u52e4"))

    allowed = {item.id for item in sample_garments}
    assert outcome.status == "success"
    assert outcome.data["recommendations"]
    assert all(
        set(item["garment_ids"]) <= allowed
        for item in outcome.data["recommendations"]
    )


def test_skill_keeps_rule_results_when_weather_fails(repo, sample_garments):
    for garment in sample_garments:
        repo.save_garment("u1", garment)

    def unavailable(city: str) -> str:
        raise TimeoutError(city)

    outcome = OutfitPlanningSkill(repo, weather_loader=unavailable).run(
        "u1",
        OutfitRequest(scene="\u901a\u52e4", city="\u676d\u5dde"),
    )

    assert outcome.status == "fallback"
    assert outcome.data["recommendations"]
    assert "\u5929\u6c14" in outcome.user_message


def test_skill_explains_incomplete_wardrobe(repo):
    outcome = OutfitPlanningSkill(repo).run("u1", OutfitRequest(scene="\u901a\u52e4"))

    assert outcome.status == "fallback"
    assert outcome.data["recommendations"] == []
    assert "\u4e0a\u88c5" in outcome.user_message and "\u4e0b\u88c5" in outcome.user_message


def test_skill_trace_is_compact_and_keeps_weather_payload_private(repo, sample_garments):
    for garment in sample_garments:
        repo.save_garment("u1", garment)

    outcome = OutfitPlanningSkill(repo, weather_loader=lambda city: "secret=hot").run(
        "u1",
        OutfitRequest(scene="\u901a\u52e4", city="\u676d\u5dde"),
    )

    assert [step.name for step in outcome.trace.steps] == [
        "load_wardrobe",
        "weather",
        "plan_outfits",
    ]
    assert len(outcome.trace.steps) <= 3
    assert all("secret=hot" not in step.summary for step in outcome.trace.steps)
    assert all(sample_garments[0].name not in step.summary for step in outcome.trace.steps)
