from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, PngImagePlugin

from storage.images import LocalImageStore, SessionImageStore


def test_session_images_are_owner_isolated():
    store = SessionImageStore({})
    ref = store.save("u1", "g1", b"image", "image/jpeg")

    assert ref.startswith("memory://")
    assert store.read("u1", ref) == b"image"
    assert store.read("u2", ref) is None


def test_session_delete_is_owner_isolated():
    store = SessionImageStore({})
    ref = store.save("u1", "g1", b"image", "image/jpeg")

    store.delete("u2", ref)

    assert store.read("u1", ref) == b"image"


def test_local_store_keeps_files_below_configured_root(tmp_path: Path, jpeg_bytes):
    root = tmp_path / "uploads"
    store = LocalImageStore(root)
    ref = store.save("../../escape", "../garment", jpeg_bytes, "image/jpeg")
    saved = (root / ref).resolve()

    assert saved.is_relative_to(root.resolve())
    assert saved.suffix == ".jpg"


def test_local_store_strips_image_metadata(tmp_path: Path):
    image = Image.new("RGB", (8, 8), "white")
    source = BytesIO()
    image.save(source, format="JPEG", exif=b"Exif\x00\x00private-metadata")
    store = LocalImageStore(tmp_path / "uploads")
    ref = store.save("u1", "g1", source.getvalue(), "image/jpeg")

    with Image.open(tmp_path / "uploads" / ref) as saved:
        assert not saved.getexif()


@pytest.mark.parametrize(
    ("image_format", "mime_type"),
    [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")],
)
def test_local_store_removes_exif_icc_xmp_and_comments(
    tmp_path: Path, image_format: str, mime_type: str
):
    exif = Image.Exif()
    exif[270] = "private-exif"
    source = BytesIO()
    options = {
        "exif": exif.tobytes(),
        "icc_profile": b"private-icc-profile",
        "xmp": b"<x:xmpmeta>private-xmp-comment</x:xmpmeta>",
    }
    if image_format == "PNG":
        pnginfo = PngImagePlugin.PngInfo()
        pnginfo.add_text("Comment", "private-comment")
        pnginfo.add_itxt("XML:com.adobe.xmp", "private-xmp-comment")
        options["pnginfo"] = pnginfo
    Image.new("RGB", (8, 8), "white").save(source, format=image_format, **options)
    assert b"private" in source.getvalue()

    store = LocalImageStore(tmp_path / "uploads")
    ref = store.save("u1", "g1", source.getvalue(), mime_type)
    saved_path = tmp_path / "uploads" / ref

    assert b"private" not in saved_path.read_bytes()
    with Image.open(saved_path) as saved:
        assert not saved.getexif()
        assert not {"icc_profile", "xmp", "comment", "Comment"} & saved.info.keys()


def test_local_store_converts_transparent_sources_for_jpeg(tmp_path: Path):
    source = BytesIO()
    Image.new("RGBA", (8, 8), (255, 255, 255, 128)).save(source, format="PNG")
    store = LocalImageStore(tmp_path / "uploads")

    ref = store.save("u1", "g1", source.getvalue(), "image/jpeg")

    with Image.open(tmp_path / "uploads" / ref) as saved:
        assert saved.mode == "RGB"


def test_local_store_rejects_refs_outside_root(tmp_path: Path):
    store = LocalImageStore(tmp_path / "uploads")

    with pytest.raises(ValueError, match="outside"):
        store.resolve("../escape.jpg")
