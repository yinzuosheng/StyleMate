"""Discover high-resolution, clearly licensed single-item wardrobe assets.

The discovery source is intentionally narrow: Wikimedia Commons files from
Auckland Museum. The collection provides stable provenance, explicit
licensing and object-style photographs with uncluttered backgrounds.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
API_URL = "https://commons.wikimedia.org/w/api.php"
MIN_SOURCE_DIMENSION = 800
ALLOWED_MIMES = {"image/jpeg", "image/png", "image/webp"}
REJECT_TITLE_TERMS = {
    "army",
    "baby",
    "child",
    "christening",
    "costume",
    "diagram",
    "doll",
    "fragment",
    "military",
    "portrait",
    "sample",
    "theatrical",
    "uniform",
    " and ",
    "top hat",
    "fastener",
    "case)",
}
REJECT_DESCRIPTION_TERMS = {
    "air force",
    "army",
    "badge",
    "boy",
    "child",
    "christening",
    "close-up",
    "close up",
    "detail photograph",
    "display case",
    "document",
    "girl",
    "infant",
    "label",
    "mannequin",
    "military",
    "naval",
    "pattern piece",
    "portrait",
    "sample card",
    "textile sample",
    "fabric sample",
    "uniform",
    "ww1",
    "ww2",
}


@dataclass(frozen=True)
class SourceSpec:
    category: str
    title_prefix: str
    subtype: str
    quota: int
    seasons: tuple[str, ...]
    styles: tuple[str, ...]


CATEGORY_TARGETS = {
    "上装": 32,
    "下装": 24,
    "外套": 20,
    "连衣裙": 16,
    "鞋履": 14,
    "包袋": 12,
    "配饰": 10,
}

# The quota on each search term is a ceiling, not a hard requirement. If a
# small museum subcategory has too few distinct objects, the next term fills
# the remaining category quota.
SEARCH_SPECS = (
    SourceSpec("上装", "Blouse", "罩衫", 13, ("春", "夏", "秋"), ("优雅", "通勤")),
    SourceSpec("上装", "Shirt", "衬衫", 10, ("春", "夏", "秋"), ("休闲", "通勤")),
    SourceSpec("上装", "Waistcoat", "马甲", 7, ("春", "秋", "冬"), ("通勤", "正式")),
    SourceSpec("上装", "Jumper", "针织衫", 1, ("秋", "冬"), ("休闲", "保暖")),
    SourceSpec("上装", "Top", "上衣", 4, ("春", "夏"), ("简约", "约会")),
    SourceSpec("下装", "Trousers", "长裤", 8, ("春", "秋", "冬"), ("通勤", "简约")),
    SourceSpec("下装", "Skirt", "半身裙", 12, ("春", "夏", "秋"), ("优雅", "通勤")),
    SourceSpec("下装", "Shorts", "短裤", 4, ("夏",), ("休闲", "运动")),
    SourceSpec("下装", "Breeches", "马裤", 5, ("春", "秋"), ("户外", "休闲")),
    SourceSpec("外套", "Coat", "大衣", 7, ("秋", "冬"), ("通勤", "保暖")),
    SourceSpec("外套", "Jacket", "夹克", 7, ("春", "夏", "秋"), ("休闲", "户外")),
    SourceSpec("外套", "Cloak", "斗篷", 3, ("秋", "冬"), ("优雅", "正式")),
    SourceSpec("外套", "Cape", "披肩外套", 3, ("春", "夏", "秋"), ("优雅", "约会")),
    SourceSpec("连衣裙", "Dress", "连衣裙", 16, ("春", "夏", "秋"), ("优雅", "约会")),
    SourceSpec("鞋履", "Shoes", "鞋履", 7, ("四季",), ("简约", "通勤")),
    SourceSpec("鞋履", "Boots", "短靴", 4, ("秋", "冬"), ("通勤", "户外")),
    SourceSpec("鞋履", "Sandals", "凉鞋", 3, ("夏",), ("休闲", "约会")),
    SourceSpec("包袋", "Handbag", "手提包", 6, ("四季",), ("通勤", "优雅")),
    SourceSpec("包袋", "Purse", "小包", 6, ("四季",), ("约会", "简约")),
    SourceSpec("配饰", "Hat", "帽子", 2, ("春", "夏", "秋"), ("休闲", "旅行")),
    SourceSpec("配饰", "Scarf", "围巾", 2, ("春", "秋", "冬"), ("优雅", "保暖")),
    SourceSpec("配饰", "Belt", "腰带", 2, ("四季",), ("简约", "通勤")),
    SourceSpec("配饰", "Gloves", "手套", 2, ("秋", "冬"), ("优雅", "保暖")),
    SourceSpec("配饰", "Necklace", "项链", 2, ("四季",), ("优雅", "正式")),
)


def _clean_html(value: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(value or ""))).strip()


def normalize_license(value: str | None) -> str | None:
    """Return a stable allowlisted license label, or ``None`` if ambiguous."""
    raw = _clean_html(value)
    compact = re.sub(r"\s+", " ", raw).strip()
    if re.match(r"^public domain(?: dedication)?(?:$|\s)", compact, re.I):
        return "Public Domain"
    if re.match(r"^cc0(?:\s|$)", compact, re.I):
        version = re.search(r"\b\d+(?:\.\d+)?\b", compact[3:])
        return f"CC0 {version.group(0)}" if version else "CC0"
    match = re.match(r"^cc\s+by(?:-sa)?(?:\s|$)", compact, re.I)
    if match:
        label = "CC BY-SA" if "-sa" in match.group(0).lower() else "CC BY"
        version = re.search(r"\d+(?:\.\d+)?", compact)
        return f"{label} {version.group(0)}" if version else label
    match = re.match(
        r"^creative commons attribution(?:-share alike| share alike)(?:\s|$)", compact, re.I
    )
    if match:
        version = re.search(r"\d+(?:\.\d+)?", compact)
        return f"CC BY-SA {version.group(0)}" if version else "CC BY-SA"
    if re.match(r"^creative commons attribution(?:\s|$)", compact, re.I):
        version = re.search(r"\d+(?:\.\d+)?", compact)
        return f"CC BY {version.group(0)}" if version else "CC BY"
    return None


def _is_matching_title(title: str, spec: SourceSpec) -> bool:
    short_title = title.removeprefix("File:").strip()
    prefix = spec.title_prefix.casefold()
    lowered = short_title.casefold()
    if not (lowered == prefix or lowered.startswith(f"{prefix},") or lowered.startswith(f"{prefix} ")):
        return False
    return not any(term in lowered for term in REJECT_TITLE_TERMS)


def candidate_from_page(page: dict, spec: SourceSpec) -> dict | None:
    """Convert a Commons API page to a validated candidate record."""
    title = str(page.get("title") or "")
    if not _is_matching_title(title, spec):
        return None
    info = (page.get("imageinfo") or [{}])[0]
    metadata = info.get("extmetadata") or {}
    license_name = normalize_license((metadata.get("LicenseShortName") or {}).get("value"))
    width, height = int(info.get("width") or 0), int(info.get("height") or 0)
    mime = str(info.get("mime") or "").lower()
    source_url = canonical_url(str(info.get("url") or ""))
    if not license_name or mime not in ALLOWED_MIMES or min(width, height) < MIN_SOURCE_DIMENSION or not source_url:
        return None
    description = _clean_html((metadata.get("ImageDescription") or {}).get("value"))
    object_name = _clean_html((metadata.get("ObjectName") or {}).get("value"))
    lowered_description = description.casefold()
    if any(term in lowered_description for term in REJECT_DESCRIPTION_TERMS):
        return None
    content_key = hashlib.sha256((description or object_name or title).casefold().encode("utf-8")).hexdigest()[:20]
    source_page = f"https://commons.wikimedia.org/wiki/{quote(title.replace(' ', '_'), safe=':/()-,.') }"
    file_path_url = (
        "https://commons.wikimedia.org/wiki/Special:FilePath/"
        + quote(title.removeprefix("File:"), safe="()-,.")
    )
    credit_raw = str((metadata.get("Credit") or {}).get("value") or "")
    museum_media_match = re.search(r"https://api\.aucklandmuseum\.com/id/media/[^\"'<>\s]+", credit_raw)
    return {
        "category": spec.category,
        "subcategory": spec.subtype,
        "title": title.removeprefix("File:"),
        "creator": _clean_html((metadata.get("Artist") or {}).get("value")) or "Auckland Museum",
        "license": license_name,
        "width": width,
        "height": height,
        "mime": mime,
        "source_url": source_url,
        "download_url": canonical_url(str(info.get("thumburl") or source_url)),
        "source_page": source_page,
        "file_path_url": file_path_url,
        "museum_media_url": museum_media_match.group(0) if museum_media_match else None,
        "description": description,
        "content_key": content_key,
        "seasons": list(spec.seasons),
        "styles": list(spec.styles),
        "season_priority": spec.seasons[0],
    }


def canonical_url(url: str) -> str:
    return url.split("#", 1)[0].split("?", 1)[0]


def _cache_key(params: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(params, sort_keys=True).encode("utf-8")).hexdigest()


def _request(
    session: requests.Session,
    params: dict[str, str],
    *,
    cache_dir: Path | None,
    sleep: Callable[[float], None],
) -> dict:
    cache_path = cache_dir / f"{_cache_key(params)}.json" if cache_dir else None
    if cache_path and cache_path.is_file():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    query = {**params, "format": "json"}
    for attempt in range(5):
        response = session.get(API_URL, params=query, timeout=30)
        if response.status_code not in {403, 429}:
            response.raise_for_status()
            payload = response.json()
            if cache_path:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            return payload
        if attempt == 4:
            response.raise_for_status()
        sleep(min(30.0, 2.0 * (2**attempt)))
    raise RuntimeError("Commons request retry loop exhausted")


def discover(*, cache_dir: Path | None = None, sleep: Callable[[float], None] = time.sleep) -> list[dict]:
    session = requests.Session()
    session.headers.update({"User-Agent": "StyleMate demo source audit/2.0 (educational project)"})
    results: list[dict] = []
    seen_urls: set[str] = set()
    seen_content: set[str] = set()
    for category, target in CATEGORY_TARGETS.items():
        category_results = 0
        for spec in (item for item in SEARCH_SPECS if item.category == category):
            spec_results = 0
            base_params = {
                "action": "query",
                "generator": "search",
                "gsrsearch": f"{spec.title_prefix} AM Auckland Museum",
                "gsrnamespace": "6",
                "gsrlimit": "50",
                "prop": "imageinfo",
                "iiprop": "url|size|mime|extmetadata",
                "iiurlwidth": "1600",
            }
            cache_hit = True
            for offset in (None, 50, 100):
                params = dict(base_params)
                if offset is not None:
                    params["gsroffset"] = str(offset)
                cache_hit = cache_hit and bool(cache_dir and (cache_dir / f"{_cache_key(params)}.json").is_file())
                payload = _request(session, params, cache_dir=cache_dir, sleep=sleep)
                for page in payload.get("query", {}).get("pages", {}).values():
                    candidate = candidate_from_page(page, spec)
                    if not candidate or candidate["source_url"] in seen_urls or candidate["content_key"] in seen_content:
                        continue
                    seen_urls.add(candidate["source_url"])
                    seen_content.add(candidate["content_key"])
                    results.append(candidate)
                    category_results += 1
                    spec_results += 1
                    if category_results >= target or spec_results >= spec.quota:
                        break
                if category_results >= target or spec_results >= spec.quota:
                    break
            if category_results >= target:
                break
            if not cache_hit:
                sleep(3.2)
        if category_results < target:
            raise RuntimeError(f"Only found {category_results}/{target} candidates for {category}")
    _ensure_all_seasons_per_category(results)
    return results


def _ensure_all_seasons_per_category(records: list[dict]) -> None:
    """Guarantee demo filters always have every category in every season."""
    for category in CATEGORY_TARGETS:
        category_records = [record for record in records if record["category"] == category]
        for index, season in enumerate(("春", "夏", "秋", "冬")):
            if any(season in record["seasons"] or "四季" in record["seasons"] for record in category_records):
                continue
            selected = category_records[index % len(category_records)]
            selected["seasons"].append(season)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "assets" / "demo" / "cc_candidates.json")
    parser.add_argument("--cache-dir", type=Path, default=ROOT / ".pytest_cache" / "commons-api")
    args = parser.parse_args()
    records = discover(cache_dir=args.cache_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"discovered {len(records)} candidates at {args.output}")


if __name__ == "__main__":
    main()
