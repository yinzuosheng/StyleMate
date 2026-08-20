"""Loading for the versioned, offline built-in knowledge corpus."""

import json
from pathlib import Path

from stylemate.rag.models import KnowledgeRecord


def load_builtin_records(path: Path) -> list[KnowledgeRecord]:
    """Load JSONL records without contacting the network."""
    records: list[KnowledgeRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(KnowledgeRecord.model_validate(json.loads(line)))
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"知识库第 {line_number} 行无效: {exc}") from exc
    return records

