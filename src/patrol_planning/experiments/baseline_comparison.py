from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Callable, Iterable, List

import pandas as pd

from patrol_planning.baselines.greedy_visibility import solve_greedy_visibility
from patrol_planning.baselines.static_checkpoints import solve_static_checkpoints
from patrol_planning.config.models import AppConfig
from patrol_planning.domain.models import HistoricalIncident, PlanningScenario
from patrol_planning.domain.routes import OfficerRoute
from patrol_planning.evaluation.pvr import calculate_pvr
from patrol_planning.evaluation.routes import covered_incident_ids, routes_are_feasible
from patrol_planning.scenarios.builder import build_poisson_scenario
from patrol_planning.solvers.grafting.dp import solve_grafting
from patrol_planning.solvers.maxp.allocation import solve_maxp
from patrol_planning.solvers.minp.greedy import solve_minp
from patrol_planning.validation.grafting import validate_grafting_result
from patrol_planning.validation.maxp import validate_maxp_result
from patrol_planning.validation.minp import validate_minp_result


@dataclass
class BaselineComparisonRecord:
    seed: int
    officer_count: int
    incident_count: int
    algorithm: str
    covered_incidents: int
    coverage_rate: float
    pvr: float
    runtime_seconds: float
    route_count: int
    feasible_routes: bool
    complete_coverage: bool
    valid: bool
    status: str


def _record(
    scenario: PlanningScenario,
    seed: int,
    officer_count: int,
    algorithm: str,
    routes: Iterable[OfficerRoute],
    runtime_seconds: float,
    valid: bool,
    status: str,
) -> BaselineComparisonRecord:
    route_list = list(routes)
    covered = covered_incident_ids(scenario, route_list)
    coverage_rate = (
        len(covered) / len(scenario.incidents)
        if scenario.incidents
        else 1.0
    )
    feasible_routes = routes_are_feasible(scenario, route_list)
    return BaselineComparisonRecord(
        seed=seed,
        officer_count=officer_count,
        incident_count=len(scenario.incidents),
        algorithm=algorithm,
        covered_incidents=len(covered),
        coverage_rate=round(coverage_rate, 6),
        pvr=calculate_pvr(scenario, route_list),
        runtime_seconds=round(runtime_seconds, 6),
        route_count=len(route_list),
        feasible_routes=feasible_routes,
        complete_coverage=len(covered) == len(scenario.incidents),
        valid=valid and feasible_routes,
        status=status,
    )


def _run_baseline(
    scenario: PlanningScenario,
    seed: int,
    officer_count: int,
    algorithm: str,
    solver: Callable[[PlanningScenario], List[OfficerRoute]],
) -> BaselineComparisonRecord:
    start = perf_counter()
    routes = solver(scenario)
    runtime = perf_counter() - start
    return _record(
        scenario,
        seed,
        officer_count,
        algorithm,
        routes,
        runtime,
        valid=True,
        status="ok",
    )


def _run_proposed(
    scenario: PlanningScenario,
    config: AppConfig,
    seed: int,
    officer_count: int,
) -> BaselineComparisonRecord:
    start = perf_counter()
    minp = solve_minp(scenario, max_labels=config.minp.max_labels)
    minp_report = validate_minp_result(scenario, minp)
    if not minp.feasible or not minp_report.valid:
        runtime = perf_counter() - start
        return _record(
            scenario,
            seed,
            officer_count,
            "MinP-MaxP-Grafting",
            minp.routes,
            runtime,
            valid=minp_report.valid,
            status="insufficient_officers" if not minp.feasible else "invalid",
        )

    maxp = solve_maxp(
        scenario,
        minp,
        cost_scale=config.maxp.cost_scale,
        random_seed=seed,
    )
    maxp_report = validate_maxp_result(scenario, minp, maxp)
    grafting = solve_grafting(scenario, minp, maxp)
    grafting_report = validate_grafting_result(scenario, minp, maxp, grafting)
    runtime = perf_counter() - start
    routes = [*grafting.grafted_minp_routes, *maxp.routes]
    valid = minp_report.valid and maxp_report.valid and grafting_report.valid
    return _record(
        scenario,
        seed,
        officer_count,
        "MinP-MaxP-Grafting",
        routes,
        runtime,
        valid=valid,
        status="ok" if valid else "invalid",
    )


def run_baseline_comparison(
    config: AppConfig,
    historical_incidents: List[HistoricalIncident],
    output_directory: Path,
) -> List[BaselineComparisonRecord]:
    records: List[BaselineComparisonRecord] = []
    for seed in config.comparison.seeds:
        for officer_count in config.comparison.officer_counts:
            case_config = config.model_copy(deep=True)
            case_config.scenario.mode = "poisson"
            case_config.scenario.random_seed = seed
            case_config.scenario.officers = officer_count
            scenario = build_poisson_scenario(
                case_config,
                historical_incidents,
            ).scenario

            records.append(
                _run_proposed(
                    scenario,
                    case_config,
                    seed,
                    officer_count,
                )
            )
            records.append(
                _run_baseline(
                    scenario,
                    seed,
                    officer_count,
                    "Greedy Visibility",
                    solve_greedy_visibility,
                )
            )
            records.append(
                _run_baseline(
                    scenario,
                    seed,
                    officer_count,
                    "Static Checkpoints",
                    solve_static_checkpoints,
                )
            )

    output_directory.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([asdict(record) for record in records]).to_csv(
        output_directory / "baseline_comparison.csv",
        index=False,
    )
    return records
