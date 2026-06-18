from datetime import date, datetime
from pathlib import Path

from patrol_planning.config.models import AppConfig
from patrol_planning.domain.models import HistoricalIncident
from patrol_planning.scenarios.builder import (
    build_poisson_scenario,
    build_replay_scenario,
)
from patrol_planning.validation.scenario import validate_scenario


def test_replay_scenario_has_solver_independent_inputs() -> None:
    config = AppConfig.model_validate(
        {
            "run_name": "test",
            "data": {
                "csv_path": Path("unused.csv"),
                "area_name": "Central",
                "history_start": date(2023, 1, 1),
                "history_end": date(2023, 1, 2),
            },
            "grid": {"rows": 2, "columns": 2},
            "time": {"period_minutes": 30, "shifts_per_day": 3},
            "scenario": {
                "mode": "replay",
                "replay_date": date(2023, 1, 2),
                "officers": 3,
            },
        }
    )
    incidents = [
        HistoricalIncident(1, datetime(2023, 1, 1, 8), 34.0, -118.3, "THEFT", "Central"),
        HistoricalIncident(2, datetime(2023, 1, 2, 9), 34.1, -118.2, "ROBBERY", "Central"),
        HistoricalIncident(3, datetime(2023, 1, 2, 10), 34.2, -118.1, "BURGLARY", "Central"),
    ]

    result = build_replay_scenario(config, incidents)

    assert len(result.scenario.regions) == 4
    assert len(result.scenario.incidents) == 2
    assert len(result.scenario.officers) == 3
    assert len(result.scenario.vfop) == 48 * 4
    assert len(result.scenario.travel_periods) == 4 * 4
    assert validate_scenario(result.scenario).valid


def test_poisson_scenario_is_seeded_and_solver_independent() -> None:
    config = AppConfig.model_validate(
        {
            "run_name": "poisson-test",
            "data": {
                "csv_path": Path("unused.csv"),
                "area_name": "Central",
                "history_start": date(2023, 1, 1),
                "history_end": date(2023, 1, 2),
            },
            "grid": {"rows": 2, "columns": 2},
            "time": {"period_minutes": 30, "shifts_per_day": 3},
            "scenario": {
                "mode": "poisson",
                "replay_date": date(2023, 1, 2),
                "officers": 3,
                "random_seed": 7,
                "poisson_rate_scale": 10.0,
            },
        }
    )
    incidents = [
        HistoricalIncident(1, datetime(2023, 1, 1, 8), 34.0, -118.3, "THEFT", "Central"),
        HistoricalIncident(2, datetime(2023, 1, 2, 8), 34.0, -118.3, "THEFT", "Central"),
        HistoricalIncident(3, datetime(2023, 1, 2, 9), 34.2, -118.1, "ROBBERY", "Central"),
    ]

    first = build_poisson_scenario(config, incidents).scenario
    second = build_poisson_scenario(config, incidents).scenario

    assert first.incidents == second.incidents
    assert first.incidents
    assert all(incident.source_id < 0 for incident in first.incidents)
    assert all(
        incident.latitude == first.regions[incident.region_id].center_latitude
        and incident.longitude == first.regions[incident.region_id].center_longitude
        for incident in first.incidents
    )
    assert first.metadata["scenario_mode"] == "poisson"
    assert first.metadata["poisson_history_days"] == 2
    assert validate_scenario(first).valid
