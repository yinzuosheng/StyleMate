"""Download, audit and normalize the discovered CC wardrobe candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from io import BytesIO
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

import requests
from PIL import Image, ImageChops, ImageOps

ROOT = Path(__file__).resolve().parents[1]
MAX_ASSET_BYTES = 250_000
LEGACY_DEMO_IDS = (
    "demo-white-cotton-shirt",
    "demo-blue-oxford-shirt",
    "demo-black-fitted-tee",
    "demo-white-relaxed-tee",
    "demo-ivory-silk-blouse",
    "demo-oatmeal-cardigan",
    "demo-gray-turtleneck",
    "demo-navy-striped-knit",
    "demo-blue-straight-jeans",
    "demo-black-tailored-trousers",
    "demo-beige-wide-leg-trousers",
    "demo-charcoal-pencil-skirt",
    "demo-navy-pleated-skirt",
    "demo-light-denim-shorts",
    "demo-black-joggers",
    "demo-beige-trench-coat",
    "demo-black-blazer",
    "demo-light-denim-jacket",
    "demo-camel-wool-coat",
    "demo-ivory-down-jacket",
    "demo-olive-field-jacket",
    "demo-black-midi-dress",
    "demo-floral-chiffon-dress",
    "demo-beige-knit-dress",
    "demo-blue-shirt-dress",
    "demo-black-loafers",
    "demo-white-sneakers",
    "demo-nude-pumps",
    "demo-black-ankle-boots",
    "demo-beige-sandals",
    "demo-black-ballet-flats",
    "demo-black-tote-bag",
    "demo-camel-crossbody-bag",
    "demo-ivory-shoulder-bag",
    "demo-black-backpack",
    "demo-burgundy-handbag",
    "demo-beige-bucket-bag",
    "demo-black-leather-belt",
    "demo-beige-baseball-cap",
    "demo-blue-silk-scarf",
    "demo-black-sunglasses",
    "demo-pearl-necklace",
)


def canonical_source_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def download_with_retry(
    session: requests.Session,
    url: str,
    *,
    sleep: Callable[[float], None] = time.sleep,
    attempts: int = 8,
) -> bytes:
    """Download an image while respecting Commons' transient 429 responses."""
    clean_url = canonical_source_url(url)
    for attempt in range(attempts):
        response = session.get(clean_url, timeout=45)
        if response.status_code != 429:
            response.raise_for_status()
            return response.content
        if attempt == attempts - 1:
            response.raise_for_status()
        retry_after = getattr(response, "headers", {}).get("Retry-After")
        delay = float(retry_after) if retry_after and retry_after.isdigit() else min(60.0, 2.0 * (2**attempt))
        sleep(delay)
    raise RuntimeError("image download retry loop exhausted")


def _crop_to_subject(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    background = Image.new("RGB", rgb.size, rgb.getpixel((0, 0)))
    bounds = ImageChops.difference(rgb, background).point(lambda value: 255 if value > 16 else 0).getbbox()
    if not bounds:
        return rgb
    left, top, right, bottom = bounds
    padding = max(12, round(max(right - left, bottom - top) * 0.08))
    return rgb.crop(
        (
            max(0, left - padding),
            max(0, top - padding),
            min(rgb.width, right + padding),
            min(rgb.height, bottom + padding),
        )
    )


def normalize(source_bytes: bytes) -> bytes:
    with Image.open(BytesIO(source_bytes)) as source:
        source.load()
        image = _crop_to_subject(ImageOps.exif_transpose(source))
    scale = min(680 / image.width, 680 / image.height)
    image = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGB", (768, 768), "#f7f7f5")
    canvas.paste(image, ((768 - image.width) // 2, (768 - image.height) // 2))
    for quality in (88, 82, 76, 70, 64):
        output = BytesIO()
        canvas.save(output, format="WEBP", quality=quality, method=6)
        if output.tell() <= MAX_ASSET_BYTES or quality == 64:
            return output.getvalue()
    raise RuntimeError("unable to encode normalized image")


COLOR_TERMS = (
    ("black", "黑色"),
    ("white", "白色"),
    ("ivory", "象牙白"),
    ("cream", "米白色"),
    ("beige", "米色"),
    ("blue", "蓝色"),
    ("navy", "藏蓝色"),
    ("red", "红色"),
    ("burgundy", "酒红色"),
    ("green", "绿色"),
    ("olive", "橄榄绿"),
    ("brown", "棕色"),
    ("grey", "灰色"),
    ("gray", "灰色"),
    ("purple", "紫色"),
    ("pink", "粉色"),
    ("yellow", "黄色"),
    ("orange", "橙色"),
)
MATERIAL_TERMS = (
    ("silk", "真丝"),
    ("cotton", "棉"),
    ("wool", "羊毛"),
    ("leather", "皮革"),
    ("linen", "亚麻"),
    ("velvet", "丝绒"),
    ("satin", "缎面"),
    ("lace", "蕾丝"),
    ("nylon", "锦纶"),
    ("polyester", "聚酯纤维"),
)


def _metadata_value(text: str, terms: tuple[tuple[str, str], ...], fallback: str) -> str:
    lowered = text.casefold()
    for term, label in terms:
        if term in lowered:
            return label
    return fallback


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value[:52] or "item"


def _record_from_candidate(candidate: dict, index: int, filename: str) -> dict:
    description = f"{candidate.get('title', '')} {candidate.get('description', '')}"
    color = _metadata_value(description, COLOR_TERMS, "多色")
    material = _metadata_value(description, MATERIAL_TERMS, "混合材质")
    digest = hashlib.sha256(candidate["source_url"].encode("utf-8")).hexdigest()[:12]
    return {
        "id": LEGACY_DEMO_IDS[index] if index < len(LEGACY_DEMO_IDS) else f"demo-cc-{digest}",
        "name": f"{color}{candidate['subcategory']} {index + 1:02d}",
        "category": candidate["category"],
        "primary_color": color,
        "material": material,
        "seasons": candidate["seasons"],
        "styles": candidate["styles"],
        "image": filename,
        "source_id": digest,
        "license": candidate["license"],
        "creator": candidate["creator"],
        "source_url": canonical_source_url(candidate["source_url"]),
        "source_page": candidate["source_page"],
        "museum_media_url": candidate.get("museum_media_url"),
        "width": candidate["width"],
        "height": candidate["height"],
        "season_priority": candidate["season_priority"],
    }


def build_assets(
    candidates_path: Path,
    output_root: Path,
    *,
    output_manifest: Path,
    limit: int | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> list[dict]:
    candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
    output_root.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": "StyleMate demo source audit/2.0 (educational project)"})
    manifest: list[dict] = []
    for index, candidate in enumerate(candidates[:limit]):
        source_url = canonical_source_url(candidate["source_url"])
        digest = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:12]
        filename = f"cc-{candidate['category']}-{index:03d}-{_slug(candidate['title'])}-{digest}.webp"
        destination = output_root / filename
        if destination.is_file():
            image_bytes = destination.read_bytes()
        else:
            image_bytes = normalize(
                download_with_retry(
                    session,
                    candidate.get("museum_media_url") or candidate.get("file_path_url") or source_url,
                    sleep=sleep,
                )
            )
            destination.write_bytes(image_bytes)
            sleep(1.2)
        if len(image_bytes) > MAX_ASSET_BYTES:
            raise ValueError(f"normalized asset exceeds {MAX_ASSET_BYTES} bytes: {destination}")
        manifest.append(_record_from_candidate(candidate, index, filename))
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    output_manifest.write_text(
        json.dumps(
            {"version": "demo_wardrobe_v2", "legacy_ids": list(LEGACY_DEMO_IDS), "garments": manifest},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, default=ROOT / "assets" / "demo" / "cc_candidates.json")
    parser.add_argument("--output-root", type=Path, default=ROOT / "assets" / "demo" / "garments")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output-manifest", type=Path, default=ROOT / "assets" / "demo" / "wardrobe.json")
    args = parser.parse_args()
    records = build_assets(
        args.candidates,
        args.output_root,
        output_manifest=args.output_manifest,
        limit=args.limit,
    )
    print(f"downloaded and normalized {len(records)} CC assets")


if __name__ == "__main__":
    main()
