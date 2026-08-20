from stylemate.agent.middleware import ToolContext
from stylemate.agent.tools.wardrobe import (
    item_style_analysis,
    recommend_inventory_outfit,
    search_wardrobe,
    wardrobe_gap_check,
)
from stylemate.domain.models import Garment
from stylemate.repositories.session import SessionWardrobeRepository


def _garment(garment_id: str, name: str, category: str, *, color="black", styles=None):
    return Garment(
        id=garment_id,
        name=name,
        category=category,
        primary_color=color,
        seasons=["spring"],
        styles=styles or ["commute"],
        source="manual",
    )


def _context(repo):
    return ToolContext("owner-a", "demo", repo, None, None, None)


def _repository():
    repo = SessionWardrobeRepository({})
    repo.save_garment("owner-a", _garment("top-a", "白衬衫", "上装", color="white"))
    repo.save_garment("owner-a", _garment("bottom-a", "黑色长裤", "下装"))
    repo.save_garment("owner-a", _garment("shoe-a", "乐福鞋", "鞋履"))
    repo.save_garment("owner-b", _garment("top-b", "他人的衬衫", "上装"))
    return repo


def test_search_wardrobe_filters_and_never_leaks_other_owner_records():
    result = search_wardrobe({"color": "white"}, _context(_repository()))

    assert [item["id"] for item in result["garments"]] == ["top-a"]
    assert len(result["garments"]) <= 20


def test_recommend_inventory_outfit_returns_only_owned_garments():
    result = recommend_inventory_outfit(
        {"scene": "通勤", "candidate_garment_ids": ["top-a", "bottom-a", "shoe-a", "top-b"]},
        _context(_repository()),
    )

    recommendations = result["recommendations"]
    assert 1 <= len(recommendations) <= 3
    assert all("top-b" not in item["garment_ids"] for item in recommendations)
    assert all(set(item["garment_ids"]) <= {"top-a", "bottom-a", "shoe-a"} for item in recommendations)


def test_gap_check_and_style_analysis_derive_their_data_from_owned_wardrobe():
    context = _context(_repository())

    gaps = wardrobe_gap_check({"season": "春"}, context)
    analysis = item_style_analysis({"garment_id": "top-a"}, context)

    assert "他人的衬衫" not in str(gaps)
    assert "上装" in gaps["owned_categories"]
    assert analysis["found"] is True
    assert analysis["garment_id"] == "top-a"


def test_style_analysis_does_not_resolve_another_owners_garment():
    result = item_style_analysis({"garment_id": "top-b"}, _context(_repository()))

    assert result == {"found": False, "message": "未在您的衣橱中找到该衣物。"}


def test_outfit_tool_automatically_applies_confirmed_color_preference():
    repo = _repository()
    repo.save_garment(
        "owner-a", _garment("top-red", "红色针织衫", "上装", color="红色")
    )
    repo.save_profile("owner-a", {"color_preference": "红色"})

    result = recommend_inventory_outfit({"scene": "日常"}, _context(repo))

    assert "top-red" in result["recommendations"][0]["garment_ids"]
    assert result["recommendations"][0]["score_breakdown"]["color_preference"] == 5
