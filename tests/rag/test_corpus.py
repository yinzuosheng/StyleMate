import json
from datetime import date
from pathlib import Path

from stylemate.rag.corpus import load_builtin_records


def test_builtin_corpus_covers_required_topics_and_has_auditable_sources():
    records = load_builtin_records(Path("data/knowledge/records.jsonl"))
    sources = json.loads(
        Path("data/knowledge/sources.json").read_text(encoding="utf-8")
    )
    source_dates = {
        source["url"]: date.fromisoformat(source["retrieved_at"])
        for source in sources
    }

    assert 40 <= len(records) <= 64
    assert {"fabric", "care", "size", "color", "weather", "scenario", "wardrobe", "style", "storage"} <= {
        record.topic for record in records
    }
    assert all(str(record.source_url).startswith("https://") for record in records)
    assert all(
        record.retrieved_at == source_dates[str(record.source_url)]
        for record in records
    )
    assert all(len(record.content) <= 900 for record in records)
