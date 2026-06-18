from datetime import datetime
from pathlib import Path

import pandas as pd

from patrol_planning.config.models import AppConfig
from patrol_planning.domain.models import HistoricalIncident
from patrol_planning.experiments.runner import run_experiments
from patrol_planning.experiments.baseline_comparison import (
    run_baseline_comparison,
)
from patrol_planning.experiments.final_evaluation import run_final_evaluation


def test_experiment_runner_records_feasible_case(tmp_path: Path) -> None:
    config = AppConfig.model_validate(
        {
            "run_name": "experiment",
            "data": {
                "csv_path": "unused.csv",
                "area_name": "Central",
                "history_start": "2023-01-01",
                "history_end": "2023-01-02",
            },
            "grid": {"rows": 2, "columns": 2},
            "time": {"period_minutes": 480, "shifts_per_day": 1},
            "scenario": {
                "replay_date": "2023-01-02",
                "officers": 2,
                "random_seed": 1,
            },
            "experiment": {
                "replay_dates": ["2023-01-02"],
                "officer_counts": [2],
            },
        }
    )
    incidents = [
        HistoricalIncident(
            1,
            datetime(2023, 1, 1, 0, 0),
            34.0,
            -118.2,
            "ROBBERY",
            "Central",
        ),
        HistoricalIncident(
            2,
            datetime(2023, 1, 2, 0, 0),
            34.1,
            -118.1,
            "ROBBERY",
            "Central",
        ),
    ]

    records = run_experiments(config, incidents, tmp_path)

    assert len(records) == 1
    assert records[0].feasible
    assert records[0].coverage_rate == 1.0
    saved = pd.read_csv(tmp_path / "experiments.csv")
    assert len(saved) == 1
    assert saved.loc[0, "status"] == "ok"


def test_baseline_comparison_uses_same_sampled_scenario(tmp_path: Path) -> None:
    config = AppConfig.model_validate(
        {
            "run_name": "comparison",
            "data": {
                "csv_path": "unused.csv",
                "area_name": "Central",
                "history_start": "2023-01-01",
                "history_end": "2023-01-02",
            },
            "grid": {"rows": 2, "columns": 2},
            "time": {"period_minutes": 480, "shifts_per_day": 1},
            "scenario": {
                "mode": "poisson",
                "replay_date": "2023-01-02",
                "officers": 2,
                "random_seed": 1,
                "poisson_rate_scale": 4.0,
            },
            "comparison": {"seeds": [1], "officer_counts": [2]},
        }
    )
    incidents = [
        HistoricalIncident(
            1,
            datetime(2023, 1, 1, 0, 0),
            34.0,
            -118.2,
            "ROBBERY",
            "Central",
        ),
        HistoricalIncident(
            2,
            datetime(2023, 1, 2, 0, 0),
            34.1,
            -118.1,
            "THEFT",
            "Central",
        ),
    ]

    records = run_baseline_comparison(config, incidents, tmp_path)

    assert len(records) == 3
    assert {record.algorithm for record in records} == {
        "MinP-MaxP-Grafting",
        "Greedy Visibility",
        "Static Checkpoints",
    }
    assert len({record.incident_count for record in records}) == 1
    assert all(record.feasible_routes for record in records)
    assert (tmp_path / "baseline_comparison.csv").exists()


def test_final_evaluation_finds_feasibility_boundary(tmp_path: Path) -> None:
    config = AppConfig.model_validate(
        {
            "run_name": "final-evaluation",
            "data": {
                "csv_path": "unused.csv",
                "area_name": "Central",
                "history_start": "2023-01-01",
                "history_end": "2023-01-02",
            },
            "grid": {"rows": 2, "columns": 2},
            "time": {"period_minutes": 480, "shifts_per_day": 1},
            "scenario": {
                "mode": "poisson",
                "replay_date": "2023-01-02",
                "officers": 2,
                "random_seed": 1,
                "poisson_rate_scale": 4.0,
            },
            "final_evaluation": {
                "seeds": [1],
                "officer_counts": [1, 2],
                "grids": [{"rows": 2, "columns": 2}],
                "non_primary_seed_limit": 1,
            },
        }
    )
    incidents = [
        HistoricalIncident(
            1,
            datetime(2023, 1, 1, 0, 0),
            34.0,
            -118.2,
            "ROBBERY",
            "Central",
        ),
        HistoricalIncident(
            2,
            datetime(2023, 1, 2, 0, 0),
            34.1,
            -118.1,
            "ROBBERY",
            "Central",
        ),
    ]

    records = run_final_evaluation(config, incidents, tmp_path)

    assert len(records) == 2
    assert len({record.minp_required for record in records}) == 1
    assert all(record.valid for record in records)
    assert (tmp_path / "final_evaluation.csv").exists()
