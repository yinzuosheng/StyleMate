import json

from evaluation.run_eval import run_evaluation


def test_evaluation_writes_metrics_from_ten_cases(tmp_path):
    """Catches an evaluator that omits a case or does not persist its metrics."""
    target = tmp_path / "evaluation.json"

    result = run_evaluation(target)

    saved = json.loads(target.read_text(encoding="utf-8"))
    assert result == saved
    assert saved["case_count"] == 10
    for key in (
        "inventory_valid_rate",
        "constraint_pass_rate",
        "fallback_success_rate",
    ):
        assert 0.0 <= saved[key] <= 1.0
