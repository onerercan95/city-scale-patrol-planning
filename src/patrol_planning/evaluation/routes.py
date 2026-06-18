from __future__ import annotations

from typing import Iterable, Set

from patrol_planning.domain.models import PlanningScenario
from patrol_planning.domain.routes import OfficerRoute


def covered_incident_ids(
    scenario: PlanningScenario,
    routes: Iterable[OfficerRoute],
) -> Set[str]:
    visits_by_period = {}
    for route in routes:
        for visit in route.visits:
            visits_by_period.setdefault(visit.period, set()).add(visit.region_id)

    covered: Set[str] = set()
    for incident in scenario.incidents:
        for region_id in visits_by_period.get(incident.period, set()):
            travel = scenario.travel_periods[(region_id, incident.region_id)]
            if travel <= incident.response_limit_periods:
                covered.add(incident.request_id)
                break
    return covered


def routes_are_feasible(
    scenario: PlanningScenario,
    routes: Iterable[OfficerRoute],
) -> bool:
    officer_ids = set()
    region_ids = {region.region_id for region in scenario.regions}
    for route in routes:
        if route.officer_id in officer_ids:
            return False
        officer_ids.add(route.officer_id)
        if route.officer_id not in scenario.officers:
            return False
        if not 0 <= route.shift < scenario.shifts_per_day:
            return False

        start = route.shift * scenario.periods_per_shift
        end = start + scenario.periods_per_shift
        visits = sorted(route.visits, key=lambda visit: visit.period)
        if visits != route.visits:
            return False
        if len({visit.period for visit in visits}) != len(visits):
            return False
        if any(
            visit.region_id not in region_ids
            or not start <= visit.period < end
            for visit in visits
        ):
            return False
        for previous, current in zip(visits, visits[1:]):
            travel = scenario.travel_periods[
                (previous.region_id, current.region_id)
            ]
            if previous.period + travel + 1 > current.period:
                return False
    return True
