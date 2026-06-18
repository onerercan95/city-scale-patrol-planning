from __future__ import annotations

from random import Random
from typing import Dict, List, Tuple

from patrol_planning.domain.models import PlanningScenario
from patrol_planning.domain.routes import MaxPResult, MinPResult, OfficerRoute
from patrol_planning.evaluation.pvr import calculate_pvr
from patrol_planning.solvers.maxp.flow import FixedShiftSolution, solve_fixed_shift


def solve_maxp(
    scenario: PlanningScenario,
    minp_result: MinPResult,
    cost_scale: int = 10_000,
    random_seed: int = 42,
) -> MaxPResult:
    minp_officers = {route.officer_id for route in minp_result.routes}
    remaining_officers = [
        officer_id for officer_id in scenario.officers if officer_id not in minp_officers
    ]
    allocation = {shift: 0 for shift in range(scenario.shifts_per_day)}
    random = Random(random_seed)
    for _ in remaining_officers:
        allocation[random.randrange(scenario.shifts_per_day)] += 1

    cache: Dict[Tuple[int, int], FixedShiftSolution] = {}

    def solution(shift: int, count: int) -> FixedShiftSolution:
        key = (shift, count)
        if key not in cache:
            cache[key] = solve_fixed_shift(
                scenario,
                shift,
                count,
                cost_scale=cost_scale,
            )
        return cache[key]

    while remaining_officers:
        best_move = None
        best_improvement = 0.0
        for shift_out in range(scenario.shifts_per_day):
            count_out = allocation[shift_out]
            if count_out == 0:
                continue
            loss = solution(shift_out, count_out).pvr - solution(
                shift_out,
                count_out - 1,
            ).pvr
            for shift_in in range(scenario.shifts_per_day):
                if shift_in == shift_out:
                    continue
                count_in = allocation[shift_in]
                gain = solution(shift_in, count_in + 1).pvr - solution(
                    shift_in,
                    count_in,
                ).pvr
                improvement = gain - loss
                move_key = (improvement, -shift_in, -shift_out)
                if improvement > best_improvement + 1e-9 and (
                    best_move is None
                    or move_key > best_move[0]
                ):
                    best_improvement = improvement
                    best_move = (move_key, shift_out, shift_in)
        if best_move is None:
            break
        _, shift_out, shift_in = best_move
        allocation[shift_out] -= 1
        allocation[shift_in] += 1

    routes: List[OfficerRoute] = []
    officer_index = 0
    for shift in range(scenario.shifts_per_day):
        fixed = solution(shift, allocation[shift])
        for visits in fixed.routes:
            routes.append(
                OfficerRoute(
                    officer_id=remaining_officers[officer_index],
                    shift=shift,
                    visits=list(visits),
                    covered_request_ids=[],
                )
            )
            officer_index += 1

    minp_pvr = calculate_pvr(scenario, minp_result.routes)
    maxp_pvr = calculate_pvr(scenario, routes)
    combined_pvr = calculate_pvr(scenario, [*minp_result.routes, *routes])
    alpha = minp_result.selected_officer_count / len(scenario.officers)
    return MaxPResult(
        routes=routes,
        remaining_officer_ids=remaining_officers,
        shift_allocation=allocation,
        maxp_pvr=maxp_pvr,
        minp_pvr=minp_pvr,
        combined_pvr=combined_pvr,
        alpha=round(alpha, 6),
        approximation_bound=round(1.0 - alpha, 6),
        algorithm="minimum-cost flow per shift with Algorithm 3-style local allocation",
    )
