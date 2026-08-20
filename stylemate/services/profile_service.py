from stylemate.repositories.base import WardrobeRepository

PROFILE_KEYS = (
    "height",
    "weight",
    "fit_preference",
    "style_preference",
    "color_preference",
    "scene_preference",
    "body_features",
)


class ProfileService:
    def __init__(self, repository: WardrobeRepository):
        self.repository = repository

    def get(self, owner_id: str) -> dict[str, str]:
        return self.repository.get_profile(owner_id)

    def merge(
        self, owner_id: str, updates: dict[str, str]
    ) -> tuple[dict[str, str], list[str]]:
        merged = self.get(owner_id)
        conflicts: list[str] = []
        for key, incoming in updates.items():
            value = str(incoming).strip()
            existing = str(merged.get(key, "")).strip()
            if existing and value and existing != value:
                conflicts.append(key)
            elif not existing:
                merged[key] = value
        self.repository.save_profile(owner_id, merged)
        return merged, conflicts

    def replace(self, owner_id: str, profile: dict[str, str]) -> dict[str, str]:
        normalized = {key: str(profile.get(key, "")).strip() for key in PROFILE_KEYS}
        self.repository.save_profile(owner_id, normalized)
        return normalized
