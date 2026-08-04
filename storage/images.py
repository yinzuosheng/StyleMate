"""Owner-isolated image storage implementations."""

import hashlib
import uuid
from io import BytesIO
from pathlib import Path
from typing import Protocol

from PIL import Image


MIME_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MIME_FORMATS = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}


class ImageStore(Protocol):
    def save(self, owner_id: str, garment_id: str, image_bytes: bytes, mime_type: str) -> str: ...

    def read(self, owner_id: str, image_ref: str) -> bytes | None: ...

    def delete(self, owner_id: str, image_ref: str) -> None: ...


class SessionImageStore:
    def __init__(self, state: dict):
        self.state = state
        self.state.setdefault("images", {})

    def save(self, owner_id: str, garment_id: str, image_bytes: bytes, mime_type: str) -> str:
        del garment_id, mime_type
        image_ref = f"memory://{uuid.uuid4()}"
        self.state["images"].setdefault(owner_id, {})[image_ref] = bytes(image_bytes)
        return image_ref

    def read(self, owner_id: str, image_ref: str) -> bytes | None:
        return self.state["images"].get(owner_id, {}).get(image_ref)

    def delete(self, owner_id: str, image_ref: str) -> None:
        self.state["images"].get(owner_id, {}).pop(image_ref, None)


class LocalImageStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, owner_id: str, garment_id: str, image_bytes: bytes, mime_type: str) -> str:
        del garment_id
        try:
            extension = MIME_EXTENSIONS[mime_type]
            image_format = MIME_FORMATS[mime_type]
        except KeyError as exc:
            raise ValueError("Unsupported image MIME type") from exc

        owner_directory = self._owner_directory(owner_id)
        owner_directory.mkdir(parents=True, exist_ok=True)
        image_ref = (owner_directory.relative_to(self.root) / f"{uuid.uuid4()}{extension}").as_posix()
        destination = self.resolve(image_ref)
        image = self._decoded_image(image_bytes, image_format)
        image.save(destination, format=image_format)
        return image_ref

    def read(self, owner_id: str, image_ref: str) -> bytes | None:
        if not self._belongs_to_owner(owner_id, image_ref):
            return None
        path = self.resolve(image_ref)
        return path.read_bytes() if path.is_file() else None

    def delete(self, owner_id: str, image_ref: str) -> None:
        if not self._belongs_to_owner(owner_id, image_ref):
            return
        path = self.resolve(image_ref)
        if path.is_file():
            path.unlink()

    def resolve(self, image_ref: str) -> Path:
        candidate = (self.root / image_ref).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("Image reference resolves outside the configured root") from exc
        return candidate

    @staticmethod
    def _decoded_image(image_bytes: bytes, image_format: str) -> Image.Image:
        try:
            with Image.open(BytesIO(image_bytes)) as source:
                source.load()
                image = source.copy()
        except (OSError, ValueError) as exc:
            raise ValueError("Image bytes cannot be decoded") from exc
        if image_format == "JPEG" and image.mode != "RGB":
            image = image.convert("RGB")
        elif image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGB")
        clean = Image.new(image.mode, image.size)
        clean.paste(image)
        return clean

    def _owner_directory(self, owner_id: str) -> Path:
        owner_token = hashlib.sha256(owner_id.encode("utf-8")).hexdigest()
        return self.root / owner_token

    def _belongs_to_owner(self, owner_id: str, image_ref: str) -> bool:
        try:
            return self.resolve(image_ref).parent == self._owner_directory(owner_id)
        except ValueError:
            return False
