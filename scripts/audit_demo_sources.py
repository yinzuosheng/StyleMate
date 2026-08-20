"""Audit the checked-in v2 demo wardrobe and its CC provenance."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_LICENSES = {
    "CC0",
    "CC0 1.0",
    "CC BY 3.0",
    "CC BY 4.0",
    "CC BY-SA 3.0",
    "CC BY-SA 4.0",
    "Public Domain",
}
TARGETS = {"上装": 32, "下装": 24, "外套": 20, "连衣裙": 16, "鞋履": 14, "包袋": 12, "配饰": 10}


def audit(manifest_path: Path) -> dict:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = payload.get("garments") or []
    errors: list[str] = []
    if payload.get("version") != "demo_wardrobe_v2":
        errors.append("manifest version must be demo_wardrobe_v2")
    if len(records) != 128:
        errors.append(f"expected 128 records, found {len(records)}")
    category_counts = Counter(record.get("category") for record in records)
    if category_counts != Counter(TARGETS):
        errors.append(f"category quotas do not match: {dict(category_counts)}")
    source_urls = [record.get("source_url") for record in records]
    if len(source_urls) != len(set(source_urls)):
        errors.append("source URLs are not unique")

    asset_root = manifest_path.parent / "garments"
    for record in records:
        record_id = record.get("id", "<missing-id>")
        missing = [
            field
            for field in ("license", "creator", "source_url", "source_page", "width", "height", "season_priority")
            if not record.get(field)
        ]
        if missing:
            errors.append(f"{record_id}: missing provenance {', '.join(missing)}")
        if record.get("license") not in ALLOWED_LICENSES:
            errors.append(f"{record_id}: license is not allowlisted")
        if min(int(record.get("width") or 0), int(record.get("height") or 0)) < 800:
            errors.append(f"{record_id}: source dimensions are below 800px")
        image_path = asset_root / str(record.get("image") or "")
        if not image_path.is_file():
            errors.append(f"{record_id}: missing asset {image_path}")
            continue
        if image_path.stat().st_size > 250_000:
            errors.append(f"{record_id}: asset exceeds 250KB")
        try:
            with Image.open(image_path) as image:
                if image.format != "WEBP" or image.size != (768, 768):
                    errors.append(f"{record_id}: asset must be 768x768 WebP")
        except OSError as exc:
            errors.append(f"{record_id}: image decode failed ({exc})")

    season_counts = {}
    for season in ("春", "夏", "秋", "冬"):
        seasonal = [record for record in records if season in record.get("seasons", []) or "四季" in record.get("seasons", [])]
        season_counts[season] = len(seasonal)
        if len(seasonal) < 25 or {record.get("category") for record in seasonal} != set(TARGETS):
            errors.append(f"{season}: seasonal quota or category coverage failed")
    return {
        "version": payload.get("version"),
        "records": len(records),
        "categories": dict(category_counts),
        "seasons": season_counts,
        "licenses": dict(Counter(record.get("license") for record in records)),
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "assets" / "demo" / "wardrobe.json")
    args = parser.parse_args()
    report = audit(args.manifest)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
