import json
from collections import Counter
from pathlib import Path

from PIL import Image, ImageChops

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = PROJECT_ROOT / "assets" / "demo" / "wardrobe.json"
EXPECTED_CATEGORY_COUNTS = {
    "上装": 32,
    "下装": 24,
    "外套": 20,
    "连衣裙": 16,
    "鞋履": 14,
    "包袋": 12,
    "配饰": 10,
}
ALLOWED_LICENSES = {"CC0", "CC0 1.0", "CC BY 3.0", "CC BY 4.0", "CC BY-SA 3.0", "CC BY-SA 4.0", "Public Domain"}


def _records() -> list[dict]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["garments"]


def test_demo_wardrobe_manifest_has_expected_category_coverage():
    records = _records()

    assert len(records) == 128
    assert len({record["id"] for record in records}) == 128
    assert Counter(record["category"] for record in records) == EXPECTED_CATEGORY_COUNTS


def test_demo_wardrobe_manifest_has_complete_metadata():
    for record in _records():
        assert record["id"].startswith("demo-")
        assert record["name"].strip()
        assert record["primary_color"].strip()
        assert record["material"].strip()
        assert record["seasons"]
        assert record["styles"]
        assert record["image"].endswith(".webp")
        assert record["license"] in ALLOWED_LICENSES
        assert record["creator"].strip()
        assert record["source_url"].startswith("https://")
        assert record["source_page"].startswith("https://commons.wikimedia.org/wiki/")
        assert record["width"] >= 800
        assert record["height"] >= 800
        assert record["season_priority"] in record["seasons"] or "四季" in record["seasons"]


def test_demo_wardrobe_manifest_has_balanced_seasonal_coverage():
    records = _records()
    for season in ("春", "夏", "秋", "冬"):
        seasonal = [record for record in records if season in record["seasons"] or "四季" in record["seasons"]]
        assert len(seasonal) >= 25
        assert {record["category"] for record in seasonal} == set(EXPECTED_CATEGORY_COUNTS)


def test_demo_wardrobe_manifest_has_unique_cc_provenance():
    records = _records()
    assert len({record["source_url"] for record in records}) == len(records)
    assert all(record["license"].startswith(("CC", "Public Domain")) for record in records)


def test_demo_wardrobe_images_are_square_webp_assets():
    asset_root = MANIFEST_PATH.parent / "garments"

    for record in _records():
        image_path = asset_root / record["image"]
        assert image_path.is_file(), image_path
        assert image_path.stat().st_size <= 250_000, image_path
        with Image.open(image_path) as image:
            assert image.format == "WEBP"
            assert image.size == (768, 768)
            background = Image.new("RGB", image.size, image.convert("RGB").getpixel((0, 0)))
            foreground = ImageChops.difference(image.convert("RGB"), background)
            bounds = foreground.point(lambda value: 255 if value > 12 else 0).getbbox()
            assert bounds is not None
            assert max(bounds[2] - bounds[0], bounds[3] - bounds[1]) >= 300

