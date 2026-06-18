from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List

import pandas as pd


@dataclass(frozen=True)
class SuccessCriterionResult:
    name: str
    status: str
    passed: bool
    evidence: str
    limitation: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def evaluate_coverage_correctness(records: pd.DataFrame) -> SuccessCriterionResult:
    """Criterion 1: every feasible patrol plan must satisfy hard IR coverage."""
    if records.empty:
        return SuccessCriterionResult(
            name="Incident coverage correctness",
            status="NOT_TESTED",
            passed=False,
            evidence="No final-evaluation records were available.",
        )

    feasible = records[records["feasible"].astype(bool)]
    if feasible.empty:
        return SuccessCriterionResult(
            name="Incident coverage correctness",
            status="FAIL",
            passed=False,
            evidence="No feasible patrol plans were produced.",
        )

    full_coverage = feasible["coverage_rate"].eq(1.0)
    valid = feasible["valid"].astype(bool)
    passed = bool(full_coverage.all() and valid.all())
    return SuccessCriterionResult(
        name="Incident coverage correctness",
        status="PASS" if passed else "FAIL",
        passed=passed,
        evidence=(
            f"{int(full_coverage.sum())}/{len(feasible)} feasible cases had 100% "
            f"incident coverage; {int(valid.sum())}/{len(feasible)} feasible cases "
            "passed independent validation."
        ),
        limitation=(
            ""
            if passed
            else "At least one feasible case failed full coverage or validation."
        ),
    )


def evaluate_visibility_improvement(records: pd.DataFrame) -> SuccessCriterionResult:
    """Criterion 2: the final plan should improve visibility after coverage."""
    if records.empty:
        return SuccessCriterionResult(
            name="Visibility improvement",
            status="NOT_TESTED",
            passed=False,
            evidence="No final-evaluation records were available.",
        )

    feasible = records[records["feasible"].astype(bool)]
    if feasible.empty:
        return SuccessCriterionResult(
            name="Visibility improvement",
            status="FAIL",
            passed=False,
            evidence="No feasible patrol plans were available for PVR evaluation.",
        )

    positive_gain = feasible["grafting_gain"].gt(0.0)
    max_pvr = float(feasible["grafted_pvr"].max())
    passed = bool(positive_gain.all() and max_pvr > 0.0)
    return SuccessCriterionResult(
        name="Visibility improvement",
        status="PASS" if passed else "FAIL",
        passed=passed,
        evidence=(
            f"{int(positive_gain.sum())}/{len(feasible)} feasible cases gained PVR "
            f"from grafting; best final PVR was {max_pvr:.3f}."
        ),
        limitation=(
            ""
            if passed
            else "At least one feasible plan did not gain visibility after grafting."
        ),
    )


def evaluate_runtime_reliability(
    records: pd.DataFrame,
    max_seconds: float = 60.0,
) -> SuccessCriterionResult:
    """Criterion 3: final evaluation should be valid, untruncated, and fast."""
    if records.empty:
        return SuccessCriterionResult(
            name="Runtime and reliability",
            status="NOT_TESTED",
            passed=False,
            evidence="No final-evaluation records were available.",
        )

    valid = records["valid"].astype(bool)
    untruncated = ~records["minp_search_truncated"].astype(bool)
    max_runtime = float(records["total_solver_seconds"].max())
    passed = bool(valid.all() and untruncated.all() and max_runtime <= max_seconds)
    return SuccessCriterionResult(
        name="Runtime and reliability",
        status="PASS" if passed else "FAIL",
        passed=passed,
        evidence=(
            f"{int(valid.sum())}/{len(records)} records were valid; "
            f"{int(untruncated.sum())}/{len(records)} had no MinP truncation; "
            f"maximum solver runtime was {max_runtime:.3f}s."
        ),
        limitation=(
            ""
            if passed
            else f"At least one record was invalid, truncated, or above {max_seconds:.1f}s."
        ),
    )


def assess_success_criteria_from_artifacts(
    output_directory: Path,
    max_seconds: float = 60.0,
) -> List[SuccessCriterionResult]:
    """Assess the three final project success criteria from exported artifacts."""
    records_path = (
        Path(output_directory)
        / "data"
        / "final_evaluation"
        / "final_evaluation.csv"
    )
    records = pd.read_csv(records_path) if records_path.exists() else pd.DataFrame()
    return [
        evaluate_coverage_correctness(records),
        evaluate_visibility_improvement(records),
        evaluate_runtime_reliability(records, max_seconds=max_seconds),
    ]
