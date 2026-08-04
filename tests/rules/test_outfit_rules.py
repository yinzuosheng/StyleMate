from domain.models import OutfitRequest
from rules.outfit_rules import plan_outfits


def test_plan_uses_only_candidate_inventory(sample_garments):
    candidates = sample_garments[:4]
    request = OutfitRequest(
        scene="\u901a\u52e4",
        style_preference="\u7b80\u7ea6",
        candidate_garment_ids=[item.id for item in candidates],
    )

    results = plan_outfits(request, sample_garments)

    allowed = {item.id for item in candidates}
    assert 1 <= len(results) <= 3
    assert all(set(item.garment_ids) <= allowed for item in results)
    assert all(item.constraint_checks["inventory"] for item in results)


def test_plan_is_deterministic(sample_garments):
    request = OutfitRequest(scene="\u901a\u52e4")

    first = [
        item.model_dump(mode="json", exclude={"created_at"})
        for item in plan_outfits(request, sample_garments)
    ]
    second = [
        item.model_dump(mode="json", exclude={"created_at"})
        for item in plan_outfits(request, sample_garments)
    ]

    assert first == second


def test_plan_never_returns_more_than_three_outfits(sample_garments):
    results = plan_outfits(OutfitRequest(scene="\u901a\u52e4"), sample_garments, limit=10)

    assert len(results) == 3
