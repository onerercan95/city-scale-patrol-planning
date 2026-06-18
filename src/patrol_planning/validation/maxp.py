from dataclasses import asdict, dataclass, field
from typing import Dict, List, Set, Tuple

from patrol_planning.domain.models import PlanningScenario
from patrol_planning.domain.routes import MaxPResult, MinPResult
from patrol_planning.evaluation.pvr import calculate_pvr


@dataclass
class MaxPValidationReport:
    valid: bool
    errors: List[str] = field(default_factory=list)
    assigned_officer_count: int = 0
    shift_allocation: Dict[int, int] = field(default_factory=dict)
    maxp_pvr: float = 0.0
    combined_pvr: float = 0.0

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def validate_maxp_result(
    scenario: PlanningScenario,
    minp_result: MinPResult,
    result: MaxPResult,
) -> MaxPValidationReport:
    errors: List[str] = []
    minp_officers = {route.officer_id for route in minp_result.routes}
    expected_remaining = set(scenario.officers) - minp_officers
    route_officers = [route.officer_id for route in result.routes]

    if len(route_officers) != len(set(route_officers)):
        errors.append("An officer appears in more than one MaxP route")
    if set(route_officers) != expected_remaining:
        errors.append("MaxP routes do not use exactly the officers remaining after MinP")
    if set(result.remaining_officer_ids) != expected_remaining:
        errors.append("MaxP remaining-officer list is incorrect")

    actual_allocation = {shift: 0 for shift in range(scenario.shifts_per_day)}
    occupied: Set[Tuple[int, int]] = set()
    region_ids = {region.region_id for region in scenario.regions}
    for route in result.routes:
        if not 0 <= route.shift < scenario.shifts_per_day:
            errors.append(f"Officer {route.officer_id} has invalid shift {route.shift}")
            continue
        actual_allocation[route.shift] += 1
        shift_start = route.shift * scenario.periods_per_shift
        shift_end = shift_start + scenario.periods_per_shift
        if route.visits != sorted(route.visits, key=lambda visit: visit.period):
            errors.append(f"Officer {route.officer_id} visits are not period-sorted")
        if not route.visits:
            errors.append(f"Officer {route.officer_id} has an empty MaxP route")

        for visit in route.visits:
            if not shift_start <= visit.period < shift_end:
                errors.append(
                    f"Officer {route.officer_id} visits outside assigned shift"
                )
            if visit.region_id not in region_ids:
                errors.append(
                    f"Officer {route.officer_id} visits unknown region {visit.region_id}"
                )
            vertex = (visit.period, visit.region_id)
            if vertex in occupied:
                errors.append(
                    f"Region {visit.region_id}, period {visit.period} is used twice in MaxP"
                )
            occupied.add(vertex)

        for previous, current in zip(route.visits, route.visits[1:]):
            travel = scenario.travel_periods[(previous.region_id, current.region_id)]
            if previous.period + travel + 1 != current.period:
                errors.append(
                    f"Officer {route.officer_id} has invalid MaxP movement "
                    f"from ({previous.period}, {previous.region_id}) to "
                    f"({current.period}, {current.region_id})"
                )

    if actual_allocation != result.shift_allocation:
        errors.append("MaxP shift allocation disagrees with generated routes")
    if sum(result.shift_allocation.values()) != len(expected_remaining):
        errors.append("MaxP shift allocation does not assign every remaining officer")

    maxp_pvr = calculate_pvr(scenario, result.routes)
    minp_pvr = calculate_pvr(scenario, minp_result.routes)
    combined_pvr = calculate_pvr(scenario, [*minp_result.routes, *result.routes])
    if abs(maxp_pvr - result.maxp_pvr) > 1e-6:
        errors.append("MaxP PVR is incorrect")
    if abs(minp_pvr - result.minp_pvr) > 1e-6:
        errors.append("MinP PVR stored in MaxP result is incorrect")
    if abs(combined_pvr - result.combined_pvr) > 1e-6:
        errors.append("Combined PVR is incorrect")

    expected_alpha = minp_result.selected_officer_count / len(scenario.officers)
    if abs(result.alpha - expected_alpha) > 1e-6:
        errors.append("Alpha is incorrect")
    if abs(result.approximation_bound - (1.0 - expected_alpha)) > 1e-6:
        errors.append("Approximation-bound value is incorrect")

    return MaxPValidationReport(
        valid=not errors,
        errors=errors,
        assigned_officer_count=len(result.routes),
        shift_allocation=actual_allocation,
        maxp_pvr=maxp_pvr,
        combined_pvr=combined_pvr,
    )
