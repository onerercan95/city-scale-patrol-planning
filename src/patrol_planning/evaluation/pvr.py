from typing import Iterable, Set, Tuple

from patrol_planning.domain.models import PlanningScenario
from patrol_planning.domain.routes import OfficerRoute


def calculate_pvr(
    scenario: PlanningScenario,
    routes: Iterable[OfficerRoute],
) -> float:
    visible: Set[Tuple[int, int]] = {
        (visit.period, visit.region_id)
        for route in routes
        for visit in route.visits
    }
    return round(
        sum(scenario.vfop[(period, region_id)] for period, region_id in visible),
        6,
    )
