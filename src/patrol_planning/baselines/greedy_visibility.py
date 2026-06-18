from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

from patrol_planning.domain.models import PlanningScenario
from patrol_planning.domain.routes import OfficerRoute, PatrolVisit


@dataclass(frozen=True)
class _State:
    score: float
    visits: Tuple[PatrolVisit, ...]


def _marginal_reward(
    scenario: PlanningScenario,
    occupied: Set[Tuple[int, int]],
    period: int,
    region_id: int,
) -> float:
    if (period, region_id) in occupied:
        return 0.0
    return scenario.vfop[(period, region_id)]


def _best_route_for_shift(
    scenario: PlanningScenario,
    shift: int,
    occupied: Set[Tuple[int, int]],
) -> _State:
    start = shift * scenario.periods_per_shift
    end = start + scenario.periods_per_shift
    states: Dict[Tuple[int, int], _State] = {}

    for period in range(start, end):
        for region in scenario.regions:
            visit = PatrolVisit(period=period, region_id=region.region_id)
            reward = _marginal_reward(
                scenario,
                occupied,
                period,
                region.region_id,
            )
            best = _State(reward, (visit,))
            for previous_region in scenario.regions:
                travel = scenario.travel_periods[
                    (previous_region.region_id, region.region_id)
                ]
                previous_period = period - travel - 1
                if previous_period < start:
                    continue
                previous = states.get(
                    (previous_period, previous_region.region_id)
                )
                if previous is None:
                    continue
                candidate = _State(
                    previous.score + reward,
                    previous.visits + (visit,),
                )
                if (
                    candidate.score > best.score + 1e-12
                    or (
                        abs(candidate.score - best.score) <= 1e-12
                        and _path_key(candidate.visits) < _path_key(best.visits)
                    )
                ):
                    best = candidate
            states[(period, region.region_id)] = best

    return min(
        states.values(),
        key=lambda state: (
            -state.score,
            -len(state.visits),
            _path_key(state.visits),
        ),
    )


def solve_greedy_visibility(
    scenario: PlanningScenario,
) -> List[OfficerRoute]:
    occupied: Set[Tuple[int, int]] = set()
    routes: List[OfficerRoute] = []

    for officer_id in scenario.officers:
        candidates = [
            (shift, _best_route_for_shift(scenario, shift, occupied))
            for shift in range(scenario.shifts_per_day)
        ]
        shift, best = min(
            candidates,
            key=lambda item: (
                -item[1].score,
                item[0],
                _path_key(item[1].visits),
            ),
        )
        routes.append(
            OfficerRoute(
                officer_id=officer_id,
                shift=shift,
                visits=list(best.visits),
                covered_request_ids=[],
            )
        )
        occupied.update(
            (visit.period, visit.region_id) for visit in best.visits
        )
    return routes


def _path_key(visits: Tuple[PatrolVisit, ...]) -> Tuple[Tuple[int, int], ...]:
    return tuple((visit.period, visit.region_id) for visit in visits)
