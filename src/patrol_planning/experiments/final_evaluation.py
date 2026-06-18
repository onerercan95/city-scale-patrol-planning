from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from time import perf_counter
from typing import List

import pandas as pd

from patrol_planning.config.models import AppConfig, EvaluationGridConfig
from patrol_planning.domain.models import HistoricalIncident, PlanningScenario
from patrol_planning.domain.routes import MinPResult
from patrol_planning.evaluation.pvr import calculate_pvr
from patrol_planning.evaluation.routes import covered_incident_ids
from patrol_planning.scenarios.builder import build_poisson_scenario
from patrol_planning.solvers.grafting.dp import solve_grafting
from patrol_planning.solvers.maxp.allocation import solve_maxp
from patrol_planning.solvers.minp.greedy import solve_minp
from patrol_planning.validation.grafting import validate_grafting_result
from patrol_planning.validation.maxp import validate_maxp_result
from patrol_planning.validation.minp import validate_minp_result
from patrol_planning.validation.scenario import validate_scenario


@dataclass
class FinalEvaluationRecord:
    seed: int
    grid_rows: int
    grid_columns: int
    grid_regions: int
    officer_count: int
    incident_count: int
    minp_required: int
    feasible: bool
    covered_incidents: int
    coverage_rate: float
    minp_pvr: float
    combined_pvr: float
    grafted_pvr: float
    grafting_gain: float
    alpha: float
    paper_reference_bound: float
    scenario_seconds: float
    minp_seconds: float
    maxp_seconds: float
    grafting_seconds: float
    total_solver_seconds: float
    minp_search_truncated: bool
    valid: bool
    status: str


def _grid_label(grid: EvaluationGridConfig) -> str:
    return f"{grid.rows}x{grid.columns}"


def _seeds_for_grid(
    config: AppConfig,
    grid: EvaluationGridConfig,
) -> List[int]:
    is_primary = (
        grid.rows == config.grid.rows
        and grid.columns == config.grid.columns
    )
    if is_primary:
        return config.final_evaluation.seeds
    return config.final_evaluation.seeds[
        : config.final_evaluation.non_primary_seed_limit
    ]


def _minp_for_officer_count(
    full_result: MinPResult,
    officer_count: int,
    scenario: PlanningScenario,
) -> MinPResult:
    if officer_count >= full_result.selected_officer_count:
        return MinPResult(
            feasible=full_result.feasible,
            routes=full_result.routes,
            coverage=full_result.coverage,
            uncovered_request_ids=full_result.uncovered_request_ids,
            available_officers=officer_count,
            algorithm=full_result.algorithm,
            label_cap=full_result.label_cap,
            search_truncated=full_result.search_truncated,
            truncated_search_count=full_result.truncated_search_count,
            peak_nondominated_labels=full_result.peak_nondominated_labels,
        )

    routes = full_result.routes[:officer_count]
    route_officers = {route.officer_id for route in routes}
    coverage = [
        record
        for record in full_result.coverage
        if record.officer_id in route_officers
    ]
    covered = covered_incident_ids(scenario, routes)
    all_requests = {incident.request_id for incident in scenario.incidents}
    return MinPResult(
        feasible=False,
        routes=routes,
        coverage=coverage,
        uncovered_request_ids=sorted(all_requests - covered),
        available_officers=officer_count,
        algorithm=full_result.algorithm,
        label_cap=full_result.label_cap,
        search_truncated=full_result.search_truncated,
        truncated_search_count=full_result.truncated_search_count,
        peak_nondominated_labels=full_result.peak_nondominated_labels,
    )


def _infeasible_record(
    scenario: PlanningScenario,
    seed: int,
    grid: EvaluationGridConfig,
    officer_count: int,
    minp_required: int,
    partial_minp: MinPResult,
    scenario_seconds: float,
    minp_seconds: float,
) -> FinalEvaluationRecord:
    covered = covered_incident_ids(scenario, partial_minp.routes)
    coverage_rate = (
        len(covered) / len(scenario.incidents)
        if scenario.incidents
        else 1.0
    )
    return FinalEvaluationRecord(
        seed=seed,
        grid_rows=grid.rows,
        grid_columns=grid.columns,
        grid_regions=grid.rows * grid.columns,
        officer_count=officer_count,
        incident_count=len(scenario.incidents),
        minp_required=minp_required,
        feasible=False,
        covered_incidents=len(covered),
        coverage_rate=round(coverage_rate, 6),
        minp_pvr=calculate_pvr(scenario, partial_minp.routes),
        combined_pvr=0.0,
        grafted_pvr=0.0,
        grafting_gain=0.0,
        alpha=round(minp_required / officer_count, 6),
        paper_reference_bound=0.0,
        scenario_seconds=round(scenario_seconds, 6),
        minp_seconds=round(minp_seconds, 6),
        maxp_seconds=0.0,
        grafting_seconds=0.0,
        total_solver_seconds=round(minp_seconds, 6),
        minp_search_truncated=partial_minp.search_truncated,
        valid=True,
        status="insufficient_officers",
    )


def run_final_evaluation(
    config: AppConfig,
    historical_incidents: List[HistoricalIncident],
    output_directory: Path,
) -> List[FinalEvaluationRecord]:
    records: List[FinalEvaluationRecord] = []
    max_officers = max(config.final_evaluation.officer_counts)

    for grid in config.final_evaluation.grids:
        for seed in _seeds_for_grid(config, grid):
            case_config = config.model_copy(deep=True)
            case_config.grid.rows = grid.rows
            case_config.grid.columns = grid.columns
            case_config.scenario.mode = "poisson"
            case_config.scenario.random_seed = seed
            case_config.scenario.officers = max_officers

            stage_start = perf_counter()
            scenario = build_poisson_scenario(
                case_config,
                historical_incidents,
            ).scenario
            scenario_seconds = perf_counter() - stage_start
            scenario_report = validate_scenario(scenario)
            if not scenario_report.valid:
                raise RuntimeError(
                    f"Invalid scenario for grid {_grid_label(grid)}, seed {seed}"
                )

            stage_start = perf_counter()
            full_minp = solve_minp(
                scenario,
                max_labels=case_config.minp.max_labels,
            )
            minp_seconds = perf_counter() - stage_start
            full_minp_report = validate_minp_result(scenario, full_minp)
            if not full_minp.feasible or not full_minp_report.valid:
                raise RuntimeError(
                    f"MinP failed for grid {_grid_label(grid)}, seed {seed}"
                )
            minp_required = full_minp.selected_officer_count

            for officer_count in config.final_evaluation.officer_counts:
                count_scenario = replace(
                    scenario,
                    officers=list(range(1, officer_count + 1)),
                )
                count_minp = _minp_for_officer_count(
                    full_minp,
                    officer_count,
                    count_scenario,
                )
                if officer_count < minp_required:
                    records.append(
                        _infeasible_record(
                            count_scenario,
                            seed,
                            grid,
                            officer_count,
                            minp_required,
                            count_minp,
                            scenario_seconds,
                            minp_seconds,
                        )
                    )
                    continue

                minp_report = validate_minp_result(
                    count_scenario,
                    count_minp,
                )
                stage_start = perf_counter()
                maxp = solve_maxp(
                    count_scenario,
                    count_minp,
                    cost_scale=case_config.maxp.cost_scale,
                    random_seed=seed,
                )
                maxp_seconds = perf_counter() - stage_start
                maxp_report = validate_maxp_result(
                    count_scenario,
                    count_minp,
                    maxp,
                )

                stage_start = perf_counter()
                grafting = solve_grafting(
                    count_scenario,
                    count_minp,
                    maxp,
                )
                grafting_seconds = perf_counter() - stage_start
                grafting_report = validate_grafting_result(
                    count_scenario,
                    count_minp,
                    maxp,
                    grafting,
                )
                valid = (
                    minp_report.valid
                    and maxp_report.valid
                    and grafting_report.valid
                )
                records.append(
                    FinalEvaluationRecord(
                        seed=seed,
                        grid_rows=grid.rows,
                        grid_columns=grid.columns,
                        grid_regions=grid.rows * grid.columns,
                        officer_count=officer_count,
                        incident_count=len(count_scenario.incidents),
                        minp_required=minp_required,
                        feasible=True,
                        covered_incidents=minp_report.covered_request_count,
                        coverage_rate=1.0,
                        minp_pvr=maxp.minp_pvr,
                        combined_pvr=maxp.combined_pvr,
                        grafted_pvr=grafting.grafted_combined_pvr,
                        grafting_gain=grafting.grafting_gain,
                        alpha=maxp.alpha,
                        paper_reference_bound=maxp.approximation_bound,
                        scenario_seconds=round(scenario_seconds, 6),
                        minp_seconds=round(minp_seconds, 6),
                        maxp_seconds=round(maxp_seconds, 6),
                        grafting_seconds=round(grafting_seconds, 6),
                        total_solver_seconds=round(
                            minp_seconds + maxp_seconds + grafting_seconds,
                            6,
                        ),
                        minp_search_truncated=count_minp.search_truncated,
                        valid=valid,
                        status="ok" if valid else "validation_failed",
                    )
                )

    output_directory.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([asdict(record) for record in records]).to_csv(
        output_directory / "final_evaluation.csv",
        index=False,
    )
    return records
