"""Run the fixed, offline StyleMate recommendation evaluation."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stylemate.demo.sample_data import sample_garments
from stylemate.domain.models import OutfitRequest
from stylemate.repositories.session import SessionWardrobeRepository
from stylemate.rules.outfit_rules import plan_outfits
from stylemate.skills.outfit_planning import OutfitPlanningSkill

CASES_PATH = Path(__file__).with_name("cases.json")


def run_evaluation(output_path: Path) -> dict[str, float | int | str]:
    """Evaluate fixed inventory cases and write their aggregate metrics."""
    cases = _load_cases()
    garments = sample_garments()
    garments_by_id = {garment.id: garment for garment in garments}

    inventory_valid = 0
    constraint_passed = 0
    fallback_success = 0
    weather_failure_count = 0

    for case in cases:
        request = OutfitRequest(
            scene=case["scene"],
            style_preference=case["style_preference"],
            candidate_garment_ids=case["candidate_ids"],
        )
        recommendations = plan_outfits(request, garments)
        returned_ids = {
            garment_id
            for recommendation in recommendations
            for garment_id in recommendation.garment_ids
        }
        if returned_ids <= set(case["candidate_ids"]):
            inventory_valid += 1

        expected_shape = bool(recommendations) == case["expect_recommendation"]
        checks_pass = all(
            all(recommendation.constraint_checks.values())
            for recommendation in recommendations
        )
        if expected_shape and checks_pass:
            constraint_passed += 1

        if case["simulate_weather_failure"]:
            weather_failure_count += 1
            outcome = _run_weather_fallback(request, garments_by_id)
            if outcome.status == "fallback" and outcome.data["recommendations"]:
                fallback_success += 1

    case_count = len(cases)
    metrics: dict[str, float | int | str] = {
        "case_count": case_count,
        "inventory_valid_rate": _rate(inventory_valid, case_count),
        "constraint_pass_rate": _rate(constraint_passed, case_count),
        "fallback_success_rate": _rate(fallback_success, weather_failure_count),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return metrics


def _load_cases() -> list[dict[str, Any]]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def _run_weather_fallback(request: OutfitRequest, garments_by_id: dict[str, Any]):
    repository = SessionWardrobeRepository({})
    for garment_id in request.candidate_garment_ids:
        repository.save_garment("evaluation-user", garments_by_id[garment_id])

    def unavailable(_: str) -> str:
        raise TimeoutError("evaluation weather unavailable")

    request_with_city = request.model_copy(update={"city": "杭州"})
    return OutfitPlanningSkill(repository, weather_loader=unavailable).run(
        "evaluation-user", request_with_city
    )


def _rate(passed: int, total: int) -> float:
    return round(passed / total, 4) if total else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run StyleMate offline evaluation.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/evaluation.json"),
        help="Path for the generated metrics JSON.",
    )
    args = parser.parse_args()
    metrics = run_evaluation(args.output)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
