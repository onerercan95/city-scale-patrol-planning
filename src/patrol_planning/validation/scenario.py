from dataclasses import asdict, dataclass, field
from typing import Dict, List

from patrol_planning.domain.models import PlanningScenario


@dataclass
class ScenarioValidationReport:
    valid: bool
    errors: List[str] = field(default_factory=list)
    region_count: int = 0
    incident_count: int = 0
    vfop_entry_count: int = 0
    travel_entry_count: int = 0

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def validate_scenario(scenario: PlanningScenario) -> ScenarioValidationReport:
    errors: List[str] = []
    region_ids = {region.region_id for region in scenario.regions}
    expected_vfop = scenario.periods * len(region_ids)
    expected_travel = len(region_ids) * len(region_ids)

    if len(region_ids) != len(scenario.regions):
        errors.append("Region identifiers are not unique")
    if len(scenario.vfop) != expected_vfop:
        errors.append(
            f"Expected {expected_vfop} VFoP entries, found {len(scenario.vfop)}"
        )
    if len(scenario.travel_periods) != expected_travel:
        errors.append(
            f"Expected {expected_travel} travel entries, "
            f"found {len(scenario.travel_periods)}"
        )

    for incident in scenario.incidents:
        if incident.region_id not in region_ids:
            errors.append(f"{incident.request_id} references an unknown region")
        if not 0 <= incident.period < scenario.periods:
            errors.append(f"{incident.request_id} has an invalid period")
        if incident.response_limit_periods < 0:
            errors.append(f"{incident.request_id} has a negative response limit")

    for period in range(scenario.periods):
        for region_id in region_ids:
            value = scenario.vfop.get((period, region_id))
            if value is None:
                errors.append(f"Missing VFoP for period {period}, region {region_id}")
            elif not 0.0 <= value <= 1.0:
                errors.append(f"VFoP outside [0,1] for period {period}, region {region_id}")

    for source in region_ids:
        for target in region_ids:
            travel = scenario.travel_periods.get((source, target))
            if travel is None:
                errors.append(f"Missing travel time from region {source} to {target}")
            elif travel < 0:
                errors.append(f"Negative travel time from region {source} to {target}")

    return ScenarioValidationReport(
        valid=not errors,
        errors=errors,
        region_count=len(scenario.regions),
        incident_count=len(scenario.incidents),
        vfop_entry_count=len(scenario.vfop),
        travel_entry_count=len(scenario.travel_periods),
    )
