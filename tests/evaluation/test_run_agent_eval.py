import json
from pathlib import Path

import pytest

from evaluation.run_agent_eval import EmbeddingEvaluationError, run_agent_evaluation
from stylemate.rag.corpus import load_builtin_records


def test_agent_evaluation_runs_document_level_retrieval_cases(tmp_path):
    target = tmp_path / "agent-evaluation.json"

    result = run_agent_evaluation(target)

    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved == result
    assert saved["case_count"] == 101
    assert saved["retrieval_case_count"] == 60
    assert saved["graph_case_count"] == 20
    assert saved["tool_selection_accuracy"] >= 0.9
    assert saved["graph_tool_path_accuracy"] == 1.0
    assert saved["graph_contract_accuracy"] == 1.0
    assert saved["graph_write_confirmation_rate"] == 1.0
    assert saved["graph_loop_bound_pass_rate"] == 1.0
    assert saved["rag_recall_at_3"] >= 0.9
    assert saved["rag_mrr_at_5"] >= 0.9
    assert saved["rag_ndcg_at_5"] >= 0.9
    assert set(saved["retrieval_ablation"]) == {"bm25", "vector", "hybrid"}
    assert saved["retrieval_ablation"]["hybrid"]["latency_p95_ms"] > 0
    assert saved["memory_fact_recall"] >= 0.9
    assert saved["safety_pass_rate"] == 1.0


def test_rag_judgments_reference_existing_records():
    project_root = Path(__file__).resolve().parents[2]
    record_ids = {
        record.id
        for record in load_builtin_records(
            project_root / "data" / "knowledge" / "records.jsonl"
        )
    }
    cases = json.loads(
        (project_root / "evaluation" / "rag_cases.json").read_text(
            encoding="utf-8"
        )
    )

    assert len(cases) == 60
    assert len({case["id"] for case in cases}) == 60
    for case in cases:
        relevant = set(case["relevant_ids"])
        hard_negatives = set(case.get("hard_negative_ids", []))
        assert relevant
        assert relevant <= record_ids
        assert hard_negatives <= record_ids
        assert relevant.isdisjoint(hard_negatives)


class FailingEmbedding:
    model = "failing-online-evaluation"

    def embed_documents(self, _texts):
        raise RuntimeError("provider payload must not be exposed")

    def embed_query(self, _text):
        raise RuntimeError("provider payload must not be exposed")


def test_online_evaluation_fails_clearly_when_index_build_fails(tmp_path):
    target = tmp_path / "online-evaluation.json"

    with pytest.raises(EmbeddingEvaluationError, match="index build failed"):
        run_agent_evaluation(
            target,
            embedding=FailingEmbedding(),
            embedding_label="dashscope_text_embedding_v4",
        )

    assert not target.exists()

