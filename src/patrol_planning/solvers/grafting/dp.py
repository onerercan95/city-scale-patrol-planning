from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from patrol_planning.domain.models import PlanningScenario
from patrol_planning.domain.routes import (
    GraftingResult,
    MaxPResult,
    MinPResult,
    OfficerRoute,
    PatrolVisit,
)
from patrol_planning.evaluation.pvr import calculate_pvr


@dataclass(frozen=True)
class _State:
    score: float
    path: Tuple[PatrolVisit, ...]


def _marginal_reward(
    scenario: PlanningScenario,
    occupied: Set[Tuple[int, int]],
    visit: PatrolVisit,
) -> float:
    if (visit.period, visit.region_id) in occupied:
        return 0.0
    return scenario.vfop[(visit.period, visit.region_id)]


def _best_window_path(
    scenario: PlanningScenario,
    start: PatrolVisit,
    end: PatrolVisit,
    occupied: Set[Tuple[int, int]],
) -> Tuple[PatrolVisit, ...]:
    if start.period >= end.period:
        return ()
    direct_travel = scenario.travel_periods[(start.region_id, end.region_id)]
    if start.period + direct_travel + 1 > end.period:
        return ()

    states: Dict[Tuple[int, int], _State] = {
        (start.period, start.region_id): _State(0.0, (start,))
    }
    best_end: Optional[_State] = None

    for period in range(start.period, end.period):
        period_states = [
            (region_id, state)
            for (state_period, region_id), state in states.items()
            if state_period == period
        ]
        for region_id, state in period_states:
            for target in scenario.regions:
                travel = scenario.travel_periods[(region_id, target.region_id)]
                arrival = period + travel + 1
                if arrival > end.period:
                    continue
                if arrival == end.period:
                    if target.region_id != end.region_id:
                        continue
                    candidate = _State(state.score, state.path + (end,))
                    if best_end is None or candidate.score > best_end.score + 1e-12:
                        best_end = candidate
                    continue

                return_travel = scenario.travel_periods[(target.region_id, end.region_id)]
                if arrival + return_travel + 1 > end.period:
                    continue
                visit = PatrolVisit(arrival, target.region_id)
                candidate = _State(
                    state.score + _marginal_reward(scenario, occupied, visit),
                    state.path + (visit,),
                )
                key = (arrival, target.region_id)
                previous = states.get(key)
                if previous is None or candidate.score > previous.score + 1e-12:
                    states[key] = candidate

    if best_end is None:
        return ()
    return best_end.path[1:-1]


def solve_grafting(
    scenario: PlanningScenario,
    minp_result: MinPResult,
    maxp_result: MaxPResult,
) -> GraftingResult:
    occupied: Set[Tuple[int, int]] = {
        (visit.period, visit.region_id)
        for route in [*minp_result.routes, *maxp_result.routes]
        for visit in route.visits
    }
    grafted_routes: List[OfficerRoute] = []
    added_by_officer: Dict[int, List[PatrolVisit]] = {}
    processed_windows = 0
    productive_windows = 0

    for route in minp_result.routes:
        required = sorted(route.visits, key=lambda visit: visit.period)
        added: List[PatrolVisit] = []
        for start, end in zip(required, required[1:]):
            processed_windows += 1
            window_visits = list(_best_window_path(scenario, start, end, occupied))
            gain = sum(
                _marginal_reward(scenario, occupied, visit)
                for visit in window_visits
            )
            if gain > 1e-12:
                productive_windows += 1
            for visit in window_visits:
                if (visit.period, visit.region_id) not in occupied:
                    occupied.add((visit.period, visit.region_id))
            added.extend(window_visits)

        added_by_officer[route.officer_id] = added
        grafted_routes.append(
            OfficerRoute(
                officer_id=route.officer_id,
                shift=route.shift,
                visits=sorted([*required, *added], key=lambda visit: visit.period),
                covered_request_ids=list(route.covered_request_ids),
            )
        )

    baseline = calculate_pvr(scenario, [*minp_result.routes, *maxp_result.routes])
    grafted = calculate_pvr(scenario, [*grafted_routes, *maxp_result.routes])
    return GraftingResult(
        grafted_minp_routes=grafted_routes,
        added_visits=added_by_officer,
        baseline_combined_pvr=baseline,
        grafted_combined_pvr=grafted,
        grafting_gain=round(grafted - baseline, 6),
        processed_window_count=processed_windows,
        productive_window_count=productive_windows,
        algorithm="Equation 12-style marginal-PVR DP over consecutive MinP subplans",
    )
