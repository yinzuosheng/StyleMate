"""Session-safe dependencies and small wardrobe mutations for the UI."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from config.runtime import RuntimeSettings
from demo.sample_data import sample_garments
from domain.models import Garment
from gateways.vision import DashScopeVisionGateway, VisionGateway
from repositories.base import WardrobeRepository
from repositories.session import SessionWardrobeRepository
from repositories.sqlite import SQLiteWardrobeRepository
from services.wardrobe_service import WardrobeService
from skills.outfit_planning import OutfitPlanningSkill
from skills.wardrobe_onboarding import WardrobeOnboardingSkill
from storage.images import ImageStore, LocalImageStore, SessionImageStore


@dataclass
class AppContext:
    settings: RuntimeSettings
    owner_id: str
    repository: WardrobeRepository
    image_store: ImageStore
    wardrobe_service: WardrobeService
    onboarding_skill: WardrobeOnboardingSkill
    outfit_skill: OutfitPlanningSkill


def _fetch_weather_lazily(city: str) -> str:
    """Keep the retired RAG/agent stack out of no-key app startup."""
    from agent.tools.agent_tools import fetch_weather_text

    return fetch_weather_text(city)


def build_context(
    state: dict,
    settings: RuntimeSettings,
    vision: VisionGateway | None = None,
    weather_loader: Callable[[str], str] | None = None,
) -> AppContext:
    """Build per-session dependencies, retaining only the selected data store."""
    if settings.app_mode == "demo":
        repository = state.setdefault("stylemate_repository", SessionWardrobeRepository(state))
        image_store = state.setdefault("stylemate_image_store", SessionImageStore(state))
        owner_id = "demo-user"
    else:
        repository = state.setdefault(
            "stylemate_repository", SQLiteWardrobeRepository(Path("data/stylemate.db"))
        )
        image_store = state.setdefault(
            "stylemate_image_store", LocalImageStore(Path("data/uploads"))
        )
        owner_id = "local-user"

    service = WardrobeService(repository, image_store, settings.max_upload_bytes)
    actual_vision = vision or DashScopeVisionGateway(settings)
    actual_weather = weather_loader or _fetch_weather_lazily
    return AppContext(
        settings=settings,
        owner_id=owner_id,
        repository=repository,
        image_store=image_store,
        wardrobe_service=service,
        onboarding_skill=WardrobeOnboardingSkill(service, actual_vision),
        outfit_skill=OutfitPlanningSkill(repository, weather_loader=actual_weather),
    )


def load_sample_wardrobe(context: AppContext) -> int:
    """Add only sample records absent from this session/owner."""
    present_ids = {
        garment.id
        for garment in context.repository.list_garments(context.owner_id)
    }
    inserted = 0
    for garment in sample_garments():
        if garment.id not in present_ids:
            context.repository.save_garment(context.owner_id, garment)
            inserted += 1
    return inserted


def delete_garment(context: AppContext, garment_id: str) -> None:
    """Delete an owned image first, then its wardrobe record."""
    garment = context.repository.get_garment(context.owner_id, garment_id)
    if garment is None:
        return
    if garment.image_ref:
        context.image_store.delete(context.owner_id, garment.image_ref)
    context.repository.delete_garment(context.owner_id, garment_id)


def validated_garment_update(
    garment: Garment,
    *,
    name: str,
    category: str,
    primary_color: str,
    material: str | None,
    seasons: str,
    styles: str,
) -> Garment:
    """Return a fully validated edit, leaving persistence to the caller."""
    normalized = {
        "name": name.strip(),
        "category": category.strip(),
        "primary_color": primary_color.strip(),
        "material": material.strip() if material else None,
        "seasons": _split_labels(seasons),
        "styles": _split_labels(styles),
    }
    required = ("name", "category", "primary_color")
    if any(not normalized[field] for field in required):
        raise ValueError("Name, category, and color are required")
    if not normalized["seasons"] or not normalized["styles"]:
        raise ValueError("At least one season and style are required")
    return Garment.model_validate({**garment.model_dump(mode="json"), **normalized})


def _split_labels(value: str) -> list[str]:
    return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]
