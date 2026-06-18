from pathlib import Path

import pandas as pd

from patrol_planning.experiments.success_criteria import (
    assess_success_criteria_from_artifacts,
    evaluate_coverage_correctness,
    evaluate_runtime_reliability,
    evaluate_visibility_improvement,
)


def _records() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "feasible": True,
                "coverage_rate": 1.0,
                "valid": True,
                "grafting_gain": 1.5,
                "grafted_pvr": 42.0,
                "minp_search_truncated": False,
                "total_solver_seconds": 3.2,
            },
            {
                "feasible": False,
                "coverage_rate": 0.9,
                "valid": True,
                "grafting_gain": 0.0,
                "grafted_pvr": 0.0,
                "minp_search_truncated": False,
                "total_solver_seconds": 0.2,
            },
        ]
    )


def test_coverage_correctness_requires_full_valid_feasible_cases() -> None:
    criterion = evaluate_coverage_correctness(_records())

    assert criterion.passed
    assert criterion.status == "PASS"
    assert "1/1 feasible cases had 100%" in criterion.evidence


def test_coverage_correctness_fails_when_a_feasible_case_misses_incidents() -> None:
    records = _records()
    records.loc[0, "coverage_rate"] = 0.99

    criterion = evaluate_coverage_correctness(records)

    assert not criterion.passed
    assert criterion.status == "FAIL"


def test_visibility_improvement_requires_positive_grafting_gain() -> None:
    criterion = evaluate_visibility_improvement(_records())

    assert criterion.passed
    assert criterion.status == "PASS"
    assert "gained PVR" in criterion.evidence


def test_visibility_improvement_fails_when_grafting_does_not_help() -> None:
    records = _records()
    records.loc[0, "grafting_gain"] = 0.0

    criterion = evaluate_visibility_improvement(records)

    assert not criterion.passed
    assert criterion.status == "FAIL"


def test_runtime_reliability_requires_valid_untruncated_fast_records() -> None:
    criterion = evaluate_runtime_reliability(_records(), max_seconds=60.0)

    assert criterion.passed
    assert criterion.status == "PASS"
    assert "no MinP truncation" in criterion.evidence


def test_runtime_reliability_fails_when_runtime_exceeds_limit() -> None:
    records = _records()
    records.loc[0, "total_solver_seconds"] = 61.0

    criterion = evaluate_runtime_reliability(records, max_seconds=60.0)

    assert not criterion.passed
    assert criterion.status == "FAIL"


def test_artifact_assessment_reports_three_passing_final_criteria(
    tmp_path: Path,
) -> None:
    evaluation_directory = tmp_path / "data" / "final_evaluation"
    evaluation_directory.mkdir(parents=True)
    _records().iloc[[0]].to_csv(
        evaluation_directory / "final_evaluation.csv",
        index=False,
    )

    results = assess_success_criteria_from_artifacts(tmp_path)

    assert [result.name for result in results] == [
        "Incident coverage correctness",
        "Visibility improvement",
        "Runtime and reliability",
    ]
    assert all(result.status == "PASS" for result in results)
