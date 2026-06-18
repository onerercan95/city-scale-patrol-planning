from dataclasses import asdict, dataclass, field
from typing import Dict, List, Set

from patrol_planning.domain.models import PlanningIncident, PlanningScenario
from patrol_planning.domain.routes import MinPResult, OfficerRoute


@dataclass
class MinPValidationReport:
    valid: bool
    feasible: bool
    errors: List[str] = field(default_factory=list)
    covered_request_count: int = 0
    uncovered_request_count: int = 0
    selected_officer_count: int = 0

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _validate_route(
    scenario: PlanningScenario,
    route: OfficerRoute,
    incidents_by_id: Dict[str, PlanningIncident],
    errors: List[str],
) -> Set[str]:
    actual_coverage: Set[str] = set()
    shift_start = route.shift * scenario.periods_per_shift
    shift_end = shift_start + scenario.periods_per_shift
    visits = sorted(route.visits, key=lambda visit: visit.period)

    if not 0 <= route.shift < scenario.shifts_per_day:
        errors.append(f"Officer {route.officer_id} has invalid shift {route.shift}")
        return actual_coverage
    if visits != route.visits:
        errors.append(f"Officer {route.officer_id} visits are not sorted by period")
    if len({visit.period for visit in visits}) != len(visits):
        errors.append(f"Officer {route.officer_id} has multiple visits in one period")

    region_ids = {region.region_id for region in scenario.regions}
    for visit in visits:
        if not shift_start <= visit.period < shift_end:
            errors.append(
                f"Officer {route.officer_id} visits period {visit.period} outside shift"
            )
        if visit.region_id not in region_ids:
            errors.append(
                f"Officer {route.officer_id} visits unknown region {visit.region_id}"
            )

    for previous, current in zip(visits, visits[1:]):
        travel = scenario.travel_periods[(previous.region_id, current.region_id)]
        if previous.period + travel + 1 > current.period:
            errors.append(
                f"Officer {route.officer_id} cannot move from region "
                f"{previous.region_id} at period {previous.period} to region "
                f"{current.region_id} at period {current.period}"
            )

    visits_by_period = {visit.period: visit for visit in visits}
    for incident in scenario.incidents:
        visit = visits_by_period.get(incident.period)
        if visit is None:
            continue
        travel = scenario.travel_periods[(visit.region_id, incident.region_id)]
        if travel <= incident.response_limit_periods:
            actual_coverage.add(incident.request_id)

    for request_id in route.covered_request_ids:
        if request_id not in incidents_by_id:
            errors.append(
                f"Officer {route.officer_id} lists unknown request {request_id}"
            )
        elif request_id not in actual_coverage:
            errors.append(
                f"Officer {route.officer_id} claims request {request_id} "
                "without a valid patrol position"
            )
    return actual_coverage


def validate_minp_result(
    scenario: PlanningScenario,
    result: MinPResult,
) -> MinPValidationReport:
    errors: List[str] = []
    incidents_by_id = {incident.request_id: incident for incident in scenario.incidents}
    officer_ids = [route.officer_id for route in result.routes]
    if len(officer_ids) != len(set(officer_ids)):
        errors.append("An officer appears in more than one MinP route")
    if any(officer_id not in scenario.officers for officer_id in officer_ids):
        errors.append("MinP uses an officer not present in the scenario")

    covered: Set[str] = set()
    for route in result.routes:
        covered.update(_validate_route(scenario, route, incidents_by_id, errors))

    all_requests = set(incidents_by_id)
    uncovered = all_requests - covered
    if result.feasible != (not uncovered):
        errors.append("MinP feasibility flag disagrees with independently computed coverage")
    if set(result.uncovered_request_ids) != uncovered:
        errors.append("MinP uncovered-request list is incorrect")

    coverage_record_ids = [record.request_id for record in result.coverage]
    if len(coverage_record_ids) != len(set(coverage_record_ids)):
        errors.append("A request has multiple primary coverage records")
    if set(coverage_record_ids) != all_requests - set(result.uncovered_request_ids):
        errors.append("Coverage records do not match the solver's covered-request set")
    for record in result.coverage:
        if record.travel_periods > record.response_limit_periods:
            errors.append(f"Coverage record for {record.request_id} violates its limit")

    return MinPValidationReport(
        valid=not errors,
        feasible=not uncovered,
        errors=errors,
        covered_request_count=len(covered),
        uncovered_request_count=len(uncovered),
        selected_officer_count=len(result.routes),
    )
