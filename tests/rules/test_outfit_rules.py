from domain.models import Garment, OutfitRequest
from rules.outfit_rules import plan_outfits


def _garment(garment_id: str, category: str) -> Garment:
    return Garment(
        id=garment_id,
        name=garment_id,
        category=category,
        primary_color="black",
        seasons=["spring"],
        styles=["commute"],
        source="manual",
    )


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


def test_plan_rejects_single_garment_matching_both_mandatory_roles():
    all_in_one = _garment(
        "all-in-one",
        "\u4e0a\u88c5 \u4e0b\u88c5 \u978b\u5c65 \u5916\u5957",
    )

    results = plan_outfits(OutfitRequest(scene="\u901a\u52e4"), [all_in_one])

    assert results == []


def test_plan_outputs_keep_grounded_recommendation_invariants(sample_garments):
    results = plan_outfits(OutfitRequest(scene="\u901a\u52e4"), sample_garments)

    inventory_ids = {garment.id for garment in sample_garments}
    combinations = [tuple(sorted(item.garment_ids)) for item in results]
    assert all(set(item.constraint_checks) == {"inventory", "top_bottom", "style"} for item in results)
    assert all(0 <= item.score <= 100 for item in results)
    assert len(combinations) == len(set(combinations))
    assert all(set(item.garment_ids) <= inventory_ids for item in results)
