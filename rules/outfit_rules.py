"""Inventory-grounded outfit recommendation rules."""

import hashlib
from itertools import product

from domain.models import Garment, OutfitRecommendation, OutfitRequest


def plan_outfits(
    request: OutfitRequest,
    garments: list[Garment],
    limit: int = 3,
) -> list[OutfitRecommendation]:
    """Return up to ``limit`` deterministic outfits from the supplied inventory."""
    if limit <= 0:
        return []
    limit = min(limit, 3)

    allowed_ids = set(request.candidate_garment_ids)
    inventory = sorted(
        (
            garment
            for garment in garments
            if not allowed_ids or garment.id in allowed_ids
        ),
        key=lambda garment: garment.id,
    )
    tops = [garment for garment in inventory if _matches_category(garment, "\u4e0a\u88c5")]
    bottoms = [
        garment for garment in inventory if _matches_category(garment, "\u4e0b\u88c5")
    ]
    if not tops or not bottoms:
        return []

    recommendations: list[OutfitRecommendation] = []
    seen_ids: set[tuple[str, ...]] = set()
    for top, bottom in product(tops, bottoms):
        top_bottom = len({top.id, bottom.id}) == 2
        if not top_bottom:
            continue
        selected = [top, bottom]
        shoes = next(
            (
                garment
                for garment in inventory
                if _matches_category(garment, "\u978b\u5c65")
                and garment.id not in {item.id for item in selected}
            ),
            None,
        )
        if shoes is not None:
            selected.append(shoes)
        outerwear = next(
            (
                garment
                for garment in inventory
                if _matches_category(garment, "\u5916\u5957")
                and garment.id not in {item.id for item in selected}
            ),
            None,
        )
        if outerwear is not None:
            selected.append(outerwear)
        garment_ids = list(dict.fromkeys(garment.id for garment in selected))
        unique_ids = tuple(sorted(garment_ids))
        if unique_ids in seen_ids:
            continue
        seen_ids.add(unique_ids)
        style_matches = (
            request.style_preference is None
            or any(request.style_preference in garment.styles for garment in selected)
        )
        scene_matches = any(request.scene in garment.styles for garment in selected)
        score = 50
        score += 15 if shoes is not None else 0
        score += 15 if outerwear is not None else 0
        score += 10 if request.style_preference and style_matches else 0
        score += 10 if scene_matches else 0
        recommendations.append(
            OutfitRecommendation(
                id=_recommendation_id(request.scene, garment_ids),
                garment_ids=garment_ids,
                score=score,
                reason=f"{request.scene} outfit selected from your wardrobe.",
                constraint_checks={
                    "inventory": True,
                    "top_bottom": top_bottom,
                    "style": style_matches,
                },
            )
        )
        if len(recommendations) == limit:
            break
    return recommendations


def _matches_category(garment: Garment, label: str) -> bool:
    return label in garment.category


def _recommendation_id(scene: str, garment_ids: list[str]) -> str:
    payload = "|".join([scene, *sorted(garment_ids)])
    return "outfit-" + hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
