from __future__ import annotations

from typing import Dict, List

from patrol_planning.domain.models import PlanningIncident, PlanningScenario
from patrol_planning.domain.routes import (
    IncidentCoverage,
    MinPResult,
    OfficerRoute,
)
from patrol_planning.solvers.minp.single_officer import (
    SingleOfficerRoute,
    find_best_single_officer_route,
)


def _coverage_records(
    scenario: PlanningScenario,
    officer_id: int,
    route: SingleOfficerRoute,
    incidents_by_id: Dict[str, PlanningIncident],
) -> List[IncidentCoverage]:
    visits_by_period = {visit.period: visit for visit in route.visits}
    records: List[IncidentCoverage] = []
    for request_id in route.covered_request_ids:
        incident = incidents_by_id[request_id]
        visit = visits_by_period[incident.period]
        travel = scenario.travel_periods[(visit.region_id, incident.region_id)]
        records.append(
            IncidentCoverage(
                request_id=request_id,
                officer_id=officer_id,
                shift=route.shift,
                officer_region_id=visit.region_id,
                incident_region_id=incident.region_id,
                period=incident.period,
                travel_periods=travel,
                response_limit_periods=incident.response_limit_periods,
            )
        )
    return records


def solve_minp(
    scenario: PlanningScenario,
    max_labels: int = 4_000,
) -> MinPResult:
    incidents_by_id = {incident.request_id: incident for incident in scenario.incidents}
    uncovered: Dict[str, PlanningIncident] = dict(incidents_by_id)
    routes: List[OfficerRoute] = []
    coverage: List[IncidentCoverage] = []
    truncated_search_count = 0
    peak_nondominated_labels = 0

    for officer_id in scenario.officers:
        candidates = [
            find_best_single_officer_route(
                scenario,
                shift,
                list(uncovered.values()),
                max_labels=max_labels,
            )
            for shift in range(scenario.shifts_per_day)
        ]
        truncated_search_count += sum(
            route.search_was_truncated for route in candidates
        )
        peak_nondominated_labels = max(
            peak_nondominated_labels,
            *(route.peak_nondominated_labels for route in candidates),
        )
        best = min(
            candidates,
            key=lambda route: (
                -route.coverage_count,
                len(route.visits),
                route.shift,
            ),
        )
        if best.coverage_count == 0:
            break

        routes.append(
            OfficerRoute(
                officer_id=officer_id,
                shift=best.shift,
                visits=list(best.visits),
                covered_request_ids=list(best.covered_request_ids),
            )
        )
        coverage.extend(
            _coverage_records(
                scenario,
                officer_id,
                best,
                incidents_by_id,
            )
        )
        for request_id in best.covered_request_ids:
            uncovered.pop(request_id, None)
        if not uncovered:
            break

    return MinPResult(
        feasible=not uncovered,
        routes=routes,
        coverage=coverage,
        uncovered_request_ids=sorted(uncovered),
        available_officers=len(scenario.officers),
        algorithm="greedy set cover with bounded bitmask DP route search",
        label_cap=max_labels,
        search_truncated=truncated_search_count > 0,
        truncated_search_count=truncated_search_count,
        peak_nondominated_labels=peak_nondominated_labels,
    )
