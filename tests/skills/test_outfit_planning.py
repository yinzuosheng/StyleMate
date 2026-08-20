from stylemate.agent.tools.location_weather import WeatherResult
from stylemate.domain.models import OutfitRequest
from stylemate.skills.outfit_planning import OutfitPlanningSkill


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


def test_skill_adds_successful_weather_summary_to_every_recommendation(repo, sample_garments):
    for garment in sample_garments:
        repo.save_garment("u1", garment)

    outcome = OutfitPlanningSkill(
        repo,
        weather_loader=lambda city: WeatherResult(
            available=True, city=city, summary="晴，28°C"
        ),
    ).run(
        "u1",
        OutfitRequest(scene="\u901a\u52e4", city="\u676d\u5dde"),
    )

    assert [step.name for step in outcome.trace.steps] == [
        "load_wardrobe",
        "weather",
        "plan_outfits",
    ]
    assert len(outcome.trace.steps) <= 3
    assert all("晴，28°C" not in step.summary for step in outcome.trace.steps)
    assert all(sample_garments[0].name not in step.summary for step in outcome.trace.steps)
    assert {
        item["weather_note"] for item in outcome.data["recommendations"]
    } == {"晴，28°C"}


def test_skill_keeps_owner_wardrobes_isolated(repo, sample_garments):
    for garment in sample_garments:
        repo.save_garment("u1", garment)

    outcome = OutfitPlanningSkill(repo).run("u2", OutfitRequest(scene="\u901a\u52e4"))

    assert outcome.status == "fallback"
    assert outcome.data["recommendations"] == []


def test_skill_keeps_recommendation_fields_when_weather_fails(repo, sample_garments):
    for garment in sample_garments:
        repo.save_garment("u1", garment)

    request = OutfitRequest(scene="\u901a\u52e4", city="\u676d\u5dde")
    available = OutfitPlanningSkill(
        repo,
        weather_loader=lambda city: WeatherResult(
            available=True, city=city, summary="晴"
        ),
    ).run("u1", request)

    def unavailable(city: str) -> str:
        raise TimeoutError(city)

    fallback = OutfitPlanningSkill(repo, weather_loader=unavailable).run("u1", request)
    excluded = {"created_at", "weather_note"}
    available_fields = [
        {key: value for key, value in item.items() if key not in excluded}
        for item in available.data["recommendations"]
    ]
    fallback_fields = [
        {key: value for key, value in item.items() if key not in excluded}
        for item in fallback.data["recommendations"]
    ]

    assert available_fields == fallback_fields
