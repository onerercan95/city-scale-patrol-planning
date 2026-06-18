from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from time import perf_counter
from typing import List

import pandas as pd

from patrol_planning.config.models import AppConfig
from patrol_planning.domain.models import HistoricalIncident
from patrol_planning.scenarios.builder import build_replay_scenario
from patrol_planning.solvers.grafting.dp import solve_grafting
from patrol_planning.solvers.maxp.allocation import solve_maxp
from patrol_planning.solvers.minp.greedy import solve_minp
from patrol_planning.validation.grafting import validate_grafting_result
from patrol_planning.validation.maxp import validate_maxp_result
from patrol_planning.validation.minp import validate_minp_result
from patrol_planning.validation.scenario import validate_scenario


@dataclass
class ExperimentRecord:
    replay_date: str
    officer_count: int
    incident_count: int
    covered_incidents: int
    coverage_rate: float
    feasible: bool
    minp_officers: int
    maxp_officers: int
    maxp_shift_0: int
    maxp_shift_1: int
    maxp_shift_2: int
    minp_pvr: float
    maxp_pvr: float
    combined_pvr: float
    grafted_pvr: float
    grafting_gain: float
    grafting_gain_percent: float
    grafted_visits: int
    scenario_seconds: float
    minp_seconds: float
    maxp_seconds: float
    grafting_seconds: float
    total_seconds: float
    valid: bool
    status: str
    minp_search_truncated: bool = False
    minp_truncated_searches: int = 0


def _run_case(
    base_config: AppConfig,
    historical_incidents: List[HistoricalIncident],
    replay_date: date,
    officer_count: int,
) -> ExperimentRecord:
    case_start = perf_counter()
    case_config = base_config.model_copy(deep=True)
    case_config.run_name = f"{base_config.run_name}-{replay_date}-{officer_count}"
    case_config.scenario.replay_date = replay_date
    case_config.scenario.officers = officer_count

    stage_start = perf_counter()
    scenario = build_replay_scenario(case_config, historical_incidents).scenario
    scenario_seconds = perf_counter() - stage_start
    scenario_report = validate_scenario(scenario)
    if not scenario_report.valid:
        return ExperimentRecord(
            str(replay_date), officer_count, len(scenario.incidents), 0, 0.0,
            False, 0, 0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0,
            scenario_seconds, 0.0, 0.0, 0.0, perf_counter() - case_start,
            False, "scenario_validation_failed",
        )

    stage_start = perf_counter()
    minp = solve_minp(scenario, max_labels=case_config.minp.max_labels)
    minp_seconds = perf_counter() - stage_start
    minp_report = validate_minp_result(scenario, minp)
    coverage_rate = (
        minp_report.covered_request_count / len(scenario.incidents)
        if scenario.incidents
        else 1.0
    )
    if not minp_report.valid or not minp.feasible:
        status = "minp_invalid" if not minp_report.valid else "insufficient_officers"
        return ExperimentRecord(
            replay_date=str(replay_date),
            officer_count=officer_count,
            incident_count=len(scenario.incidents),
            covered_incidents=minp_report.covered_request_count,
            coverage_rate=round(coverage_rate, 6),
            feasible=False,
            minp_officers=minp.selected_officer_count,
            maxp_officers=0,
            maxp_shift_0=0,
            maxp_shift_1=0,
            maxp_shift_2=0,
            minp_pvr=0.0,
            maxp_pvr=0.0,
            combined_pvr=0.0,
            grafted_pvr=0.0,
            grafting_gain=0.0,
            grafting_gain_percent=0.0,
            grafted_visits=0,
            scenario_seconds=round(scenario_seconds, 6),
            minp_seconds=round(minp_seconds, 6),
            maxp_seconds=0.0,
            grafting_seconds=0.0,
            total_seconds=round(perf_counter() - case_start, 6),
            valid=minp_report.valid,
            status=status,
        )

    stage_start = perf_counter()
    maxp = solve_maxp(
        scenario,
        minp,
        cost_scale=case_config.maxp.cost_scale,
        random_seed=case_config.scenario.random_seed,
    )
    maxp_seconds = perf_counter() - stage_start
    maxp_report = validate_maxp_result(scenario, minp, maxp)

    stage_start = perf_counter()
    grafting = solve_grafting(scenario, minp, maxp)
    grafting_seconds = perf_counter() - stage_start
    grafting_report = validate_grafting_result(scenario, minp, maxp, grafting)
    valid = minp_report.valid and maxp_report.valid and grafting_report.valid
    gain_percent = (
        100.0 * grafting.grafting_gain / grafting.baseline_combined_pvr
        if grafting.baseline_combined_pvr
        else 0.0
    )

    return ExperimentRecord(
        replay_date=str(replay_date),
        officer_count=officer_count,
        incident_count=len(scenario.incidents),
        covered_incidents=minp_report.covered_request_count,
        coverage_rate=round(coverage_rate, 6),
        feasible=True,
        minp_officers=minp.selected_officer_count,
        maxp_officers=maxp.assigned_officer_count,
        maxp_shift_0=maxp.shift_allocation.get(0, 0),
        maxp_shift_1=maxp.shift_allocation.get(1, 0),
        maxp_shift_2=maxp.shift_allocation.get(2, 0),
        minp_pvr=maxp.minp_pvr,
        maxp_pvr=maxp.maxp_pvr,
        combined_pvr=maxp.combined_pvr,
        grafted_pvr=grafting.grafted_combined_pvr,
        grafting_gain=grafting.grafting_gain,
        grafting_gain_percent=round(gain_percent, 6),
        grafted_visits=grafting.added_visit_count,
        scenario_seconds=round(scenario_seconds, 6),
        minp_seconds=round(minp_seconds, 6),
        maxp_seconds=round(maxp_seconds, 6),
        grafting_seconds=round(grafting_seconds, 6),
        total_seconds=round(perf_counter() - case_start, 6),
        valid=valid,
        status="ok" if valid else "validation_failed",
        minp_search_truncated=minp.search_truncated,
        minp_truncated_searches=minp.truncated_search_count,
    )


def run_experiments(
    config: AppConfig,
    historical_incidents: List[HistoricalIncident],
    output_directory: Path,
) -> List[ExperimentRecord]:
    records: List[ExperimentRecord] = []
    for replay_date in config.experiment.replay_dates:
        for officer_count in config.experiment.officer_counts:
            records.append(
                _run_case(
                    config,
                    historical_incidents,
                    replay_date,
                    officer_count,
                )
            )

    output_directory.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([asdict(record) for record in records]).to_csv(
        output_directory / "experiments.csv",
        index=False,
    )
    return records
