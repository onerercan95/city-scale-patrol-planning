from dataclasses import asdict, dataclass, field
from typing import Dict, List, Set, Tuple

from patrol_planning.domain.models import PlanningScenario
from patrol_planning.domain.routes import GraftingResult, MaxPResult, MinPResult
from patrol_planning.evaluation.pvr import calculate_pvr
from patrol_planning.validation.minp import validate_minp_result


@dataclass
class GraftingValidationReport:
    valid: bool
    errors: List[str] = field(default_factory=list)
    incident_coverage_preserved: bool = False
    required_visits_preserved: bool = False
    added_visit_count: int = 0
    baseline_combined_pvr: float = 0.0
    grafted_combined_pvr: float = 0.0
    grafting_gain: float = 0.0

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def validate_grafting_result(
    scenario: PlanningScenario,
    minp_result: MinPResult,
    maxp_result: MaxPResult,
    result: GraftingResult,
) -> GraftingValidationReport:
    errors: List[str] = []
    original_by_officer = {route.officer_id: route for route in minp_result.routes}
    grafted_by_officer = {route.officer_id: route for route in result.grafted_minp_routes}
    required_preserved = set(original_by_officer) == set(grafted_by_officer)

    for officer_id, original in original_by_officer.items():
        grafted = grafted_by_officer.get(officer_id)
        if grafted is None:
            required_preserved = False
            errors.append(f"Missing grafted route for MinP officer {officer_id}")
            continue
        original_visits = {(visit.period, visit.region_id) for visit in original.visits}
        grafted_visits = {(visit.period, visit.region_id) for visit in grafted.visits}
        if not original_visits.issubset(grafted_visits):
            required_preserved = False
            errors.append(f"Required visits changed for MinP officer {officer_id}")
        expected_added = grafted_visits - original_visits
        recorded_added = {
            (visit.period, visit.region_id)
            for visit in result.added_visits.get(officer_id, [])
        }
        if expected_added != recorded_added:
            errors.append(f"Added-visit record is incorrect for officer {officer_id}")

    grafted_minp = MinPResult(
        feasible=minp_result.feasible,
        routes=result.grafted_minp_routes,
        coverage=minp_result.coverage,
        uncovered_request_ids=minp_result.uncovered_request_ids,
        available_officers=minp_result.available_officers,
        algorithm=minp_result.algorithm,
    )
    minp_validation = validate_minp_result(scenario, grafted_minp)
    if not minp_validation.valid:
        errors.extend(f"Grafted MinP: {error}" for error in minp_validation.errors)

    baseline = calculate_pvr(scenario, [*minp_result.routes, *maxp_result.routes])
    grafted = calculate_pvr(
        scenario,
        [*result.grafted_minp_routes, *maxp_result.routes],
    )
    gain = round(grafted - baseline, 6)
    if abs(result.baseline_combined_pvr - baseline) > 1e-6:
        errors.append("Stored baseline combined PVR is incorrect")
    if abs(result.grafted_combined_pvr - grafted) > 1e-6:
        errors.append("Stored grafted combined PVR is incorrect")
    if abs(result.grafting_gain - gain) > 1e-6:
        errors.append("Stored grafting gain is incorrect")
    if gain < -1e-9:
        errors.append("Grafting reduced combined PVR")

    baseline_visible: Set[Tuple[int, int]] = {
        (visit.period, visit.region_id)
        for route in [*minp_result.routes, *maxp_result.routes]
        for visit in route.visits
    }
    unique_added: Set[Tuple[int, int]] = set()
    for visits in result.added_visits.values():
        for visit in visits:
            vertex = (visit.period, visit.region_id)
            if vertex not in baseline_visible:
                unique_added.add(vertex)
    expected_gain = round(sum(scenario.vfop[vertex] for vertex in unique_added), 6)
    if abs(expected_gain - gain) > 1e-6:
        errors.append("Grafting gain does not match unique added visibility")

    return GraftingValidationReport(
        valid=not errors,
        errors=errors,
        incident_coverage_preserved=minp_validation.valid and minp_validation.feasible,
        required_visits_preserved=required_preserved,
        added_visit_count=result.added_visit_count,
        baseline_combined_pvr=baseline,
        grafted_combined_pvr=grafted,
        grafting_gain=gain,
    )
