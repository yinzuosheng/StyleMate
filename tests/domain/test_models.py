import pytest
from pydantic import ValidationError

from stylemate.domain.models import Garment, OutfitRecommendation


def test_garment_requires_core_fields():
    with pytest.raises(ValidationError):
        Garment(
            id="g-1",
            name="uncategorized item",
            category="",
            primary_color="white",
            seasons=["spring"],
            styles=["minimal"],
            source="ai",
        )


def test_recommendation_deduplicates_garment_ids():
    outfit = OutfitRecommendation(
        id="o-1",
        garment_ids=["g-1", "g-1", "g-2"],
        score=88,
        reason="Suitable for commuting",
        constraint_checks={"inventory": True},
    )

    assert outfit.garment_ids == ["g-1", "g-2"]
