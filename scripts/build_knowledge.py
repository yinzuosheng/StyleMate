"""Audit the checked-in wardrobe corpus; it never downloads sources at runtime."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stylemate.rag.corpus import load_builtin_records  # noqa: E402 - direct script execution needs ROOT on sys.path

REQUIRED_TOPICS = {"fabric", "care", "size", "color", "weather", "scenario", "wardrobe", "style", "storage"}
FORBIDDEN_COPIED_PARAGRAPHS = (
    "The Federal Trade Commission (FTC) enforces the Care Labeling Rule",
    "The combination of the five basic care symbols",
    "To get started doing your laundry, follow these steps",
)


def _load_sources(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def audit(records_path: Path, sources_path: Path) -> list[str]:
    errors: list[str] = []
    sources = _load_sources(sources_path)
    source_ids = [source.get("id") for source in sources]
    source_urls = [source.get("url") for source in sources]
    if len(source_ids) != len(set(source_ids)) or any(not value for value in source_ids):
        errors.append("sources.json duplicate or missing source id")
    if len(source_urls) != len(set(source_urls)) or any(not str(value).startswith("https://") for value in source_urls):
        errors.append("sources.json duplicate or non-HTTPS URL")
    source_by_url = {source.get("url"): source for source in sources}
    for source in sources:
        try:
            retrieved_at = date.fromisoformat(str(source.get("retrieved_at", "")))
        except ValueError:
            errors.append(f"{source.get('id')} has an invalid retrieved_at date")
            continue
        if retrieved_at > date.today():
            errors.append(f"{source.get('id')} has a future retrieved_at date")
    try:
        records = load_builtin_records(records_path)
    except (OSError, ValueError) as exc:
        return [str(exc)]
    if not 32 <= len(records) <= 64:
        errors.append(f"record count must be 32-64, got {len(records)}")
    ids = [record.id for record in records]
    if len(ids) != len(set(ids)):
        errors.append("records.jsonl has duplicate record ID")
    missing_topics = REQUIRED_TOPICS - {record.topic for record in records}
    if missing_topics:
        errors.append("missing topics: " + ", ".join(sorted(missing_topics)))
    low_coverage = [topic for topic, count in Counter(record.topic for record in records).items() if count < 3]
    if low_coverage:
        errors.append("each topic needs at least 3 records: " + ", ".join(sorted(low_coverage)))
    for record in records:
        source = source_by_url.get(str(record.source_url))
        if source is None:
            errors.append(f"{record.id} uses a URL absent from sources.json")
        else:
            if record.retrieved_at.isoformat() != source.get("retrieved_at"):
                errors.append(f"{record.id} retrieved_at differs from its source")
            if record.source_name != source.get("source_name"):
                errors.append(f"{record.id} source_name differs from its source")
        if len(record.content) < 40:
            errors.append(f"{record.id} summary is shorter than 40 characters")
        if not any("\u4e00" <= char <= "\u9fff" for char in record.content):
            errors.append(f"{record.id} does not contain an original Chinese summary")
        if any(paragraph in record.content for paragraph in FORBIDDEN_COPIED_PARAGRAPHS):
            errors.append(f"{record.id} appears to copy a source paragraph")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="validate the checked-in corpus")
    args = parser.parse_args()
    errors = audit(ROOT / "data/knowledge/records.jsonl", ROOT / "data/knowledge/sources.json")
    if errors:
        print("knowledge audit FAILED")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    if args.check:
        records = load_builtin_records(ROOT / "data/knowledge/records.jsonl")
        sources = _load_sources(ROOT / "data/knowledge/sources.json")
        print(
            f"knowledge audit PASS: {len(records)} records, "
            f"{len(REQUIRED_TOPICS)} required topics, {len(sources)} audited sources"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
