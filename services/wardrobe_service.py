"""Validation and persistence for confirmed wardrobe garments."""

import hashlib

from domain.models import Garment
from repositories.base import WardrobeRepository
from storage.images import ImageStore


ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


class UploadValidationError(ValueError):
    """Raised when a submitted garment image cannot be safely accepted."""


class WardrobeService:
    def __init__(
        self,
        repository: WardrobeRepository,
        image_store: ImageStore,
        max_upload_bytes: int,
    ):
        self.repository = repository
        self.image_store = image_store
        self.max_upload_bytes = max_upload_bytes

    def validate_upload(self, image_bytes: bytes, mime_type: str) -> None:
        if mime_type not in ALLOWED_MIME_TYPES:
            raise UploadValidationError("Only JPG, PNG, and WEBP images are supported")
        if not image_bytes:
            raise UploadValidationError("Image upload cannot be empty")
        if len(image_bytes) > self.max_upload_bytes:
            raise UploadValidationError("Image upload must be 8 MB or smaller")

    @staticmethod
    def image_hash(image_bytes: bytes) -> str:
        return hashlib.sha256(image_bytes).hexdigest()

    def find_duplicate(self, owner_id: str, image_bytes: bytes) -> Garment | None:
        return self.repository.find_garment_by_hash(owner_id, self.image_hash(image_bytes))

    def save_confirmed(
        self,
        owner_id: str,
        garment: Garment,
        image_bytes: bytes,
        mime_type: str,
    ) -> Garment:
        self.validate_upload(image_bytes, mime_type)
        image_ref = self.image_store.save(owner_id, garment.id, image_bytes, mime_type)
        saved = garment.model_copy(
            update={"image_ref": image_ref, "image_hash": self.image_hash(image_bytes)}
        )
        try:
            self.repository.save_garment(owner_id, saved)
        except Exception:
            self.image_store.delete(owner_id, image_ref)
            raise
        return saved
