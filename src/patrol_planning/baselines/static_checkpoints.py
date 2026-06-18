from __future__ import annotations

from typing import List, Tuple

from patrol_planning.domain.models import PlanningScenario
from patrol_planning.domain.routes import OfficerRoute, PatrolVisit


def solve_static_checkpoints(
    scenario: PlanningScenario,
) -> List[OfficerRoute]:
    candidates: List[Tuple[float, int, int]] = []
    for shift in range(scenario.shifts_per_day):
        start = shift * scenario.periods_per_shift
        end = start + scenario.periods_per_shift
        for region in scenario.regions:
            reward = sum(
                scenario.vfop[(period, region.region_id)]
                for period in range(start, end)
            )
            candidates.append((reward, shift, region.region_id))

    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    routes: List[OfficerRoute] = []
    for officer_id, (_, shift, region_id) in zip(
        scenario.officers,
        candidates,
    ):
        start = shift * scenario.periods_per_shift
        end = start + scenario.periods_per_shift
        routes.append(
            OfficerRoute(
                officer_id=officer_id,
                shift=shift,
                visits=[
                    PatrolVisit(period=period, region_id=region_id)
                    for period in range(start, end)
                ],
                covered_request_ids=[],
            )
        )
    return routes
