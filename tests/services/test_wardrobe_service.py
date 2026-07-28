import hashlib

import pytest

from domain.models import Garment
from services.wardrobe_service import UploadValidationError, WardrobeService
from storage.images import SessionImageStore


def make_service(repo):
    return WardrobeService(repo, SessionImageStore({}), max_upload_bytes=8 * 1024 * 1024)


def confirmed_garment(image_hash: str) -> Garment:
    return Garment(
        id="g-1",
        name="Beige coat",
        category="outerwear",
        primary_color="beige",
        seasons=["spring"],
        styles=["minimal"],
        image_hash=image_hash,
        source="ai",
    )


def test_upload_rejects_unknown_mime(repo):
    with pytest.raises(UploadValidationError, match="JPG"):
        make_service(repo).validate_upload(b"abc", "application/pdf")


def test_upload_rejects_empty_bytes(repo):
    with pytest.raises(UploadValidationError, match="empty"):
        make_service(repo).validate_upload(b"", "image/jpeg")


def test_upload_rejects_more_than_eight_mb(repo):
    with pytest.raises(UploadValidationError, match="8 MB"):
        make_service(repo).validate_upload(b"x" * (8 * 1024 * 1024 + 1), "image/jpeg")


def test_find_duplicate_is_scoped_to_owner_and_hashes_bytes(repo):
    image_bytes = b"same image"
    repo.save_garment("owner-1", confirmed_garment(hashlib.sha256(image_bytes).hexdigest()))

    service = make_service(repo)

    assert service.find_duplicate("owner-1", image_bytes).id == "g-1"
    assert service.find_duplicate("owner-2", image_bytes) is None
    assert service.image_hash(image_bytes) == hashlib.sha256(image_bytes).hexdigest()


def test_save_confirmed_stores_image_before_persisting_garment(repo, jpeg_bytes):
    store = SessionImageStore({})
    service = WardrobeService(repo, store, max_upload_bytes=8 * 1024 * 1024)
    garment = confirmed_garment(service.image_hash(jpeg_bytes))

    saved = service.save_confirmed("owner-1", garment, jpeg_bytes, "image/jpeg")

    assert saved.image_ref is not None
    assert store.read("owner-1", saved.image_ref) == jpeg_bytes
    assert repo.get_garment("owner-1", garment.id) == saved
