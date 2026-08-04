"""Session-safe dependencies and small wardrobe mutations for the UI."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from agent.tools.agent_tools import fetch_weather_text
from config.runtime import RuntimeSettings
from demo.sample_data import sample_garments
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
    actual_weather = weather_loader or fetch_weather_text
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
