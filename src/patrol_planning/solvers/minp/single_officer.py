from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from patrol_planning.domain.models import PlanningIncident, PlanningScenario
from patrol_planning.domain.routes import PatrolVisit


@dataclass(frozen=True)
class SingleOfficerRoute:
    shift: int
    visits: Tuple[PatrolVisit, ...]
    covered_request_ids: Tuple[str, ...]
    search_was_truncated: bool = False
    peak_nondominated_labels: int = 0

    @property
    def coverage_count(self) -> int:
        return len(self.covered_request_ids)


@dataclass(frozen=True)
class _Label:
    last_period: int
    last_region_id: int
    covered_mask: int
    visits: Tuple[PatrolVisit, ...]


def _count_bits(mask: int) -> int:
    return bin(mask).count("1")


def _candidate_masks(
    scenario: PlanningScenario,
    incidents: List[PlanningIncident],
    index_by_request: Dict[str, int],
) -> Dict[int, Dict[int, int]]:
    candidates: Dict[int, Dict[int, int]] = {}
    incidents_by_period: Dict[int, List[PlanningIncident]] = {}
    for incident in incidents:
        incidents_by_period.setdefault(incident.period, []).append(incident)

    for period, period_incidents in incidents_by_period.items():
        region_masks: Dict[int, int] = {}
        for region in scenario.regions:
            mask = 0
            for incident in period_incidents:
                travel = scenario.travel_periods[(region.region_id, incident.region_id)]
                if travel <= incident.response_limit_periods:
                    mask |= 1 << index_by_request[incident.request_id]
            if mask:
                region_masks[region.region_id] = mask
        candidates[period] = region_masks
    return candidates


def _prune_labels(
    labels: Iterable[_Label],
    max_labels: int,
) -> Tuple[List[_Label], int, bool]:
    exact: Dict[Tuple[int, int, int], _Label] = {}
    for label in labels:
        key = (label.last_period, label.last_region_id, label.covered_mask)
        previous = exact.get(key)
        if previous is None or len(label.visits) < len(previous.visits):
            exact[key] = label

    by_endpoint: Dict[Tuple[int, int], List[_Label]] = {}
    for label in exact.values():
        endpoint = (label.last_period, label.last_region_id)
        endpoint_labels = by_endpoint.setdefault(endpoint, [])
        if any(
            existing.covered_mask | label.covered_mask == existing.covered_mask
            for existing in endpoint_labels
        ):
            continue
        endpoint_labels[:] = [
            existing
            for existing in endpoint_labels
            if existing.covered_mask | label.covered_mask != label.covered_mask
        ]
        endpoint_labels.append(label)

    pruned = [label for endpoint_labels in by_endpoint.values() for label in endpoint_labels]
    pruned.sort(
        key=lambda label: (
            -_count_bits(label.covered_mask),
            len(label.visits),
            label.last_period,
            label.last_region_id,
            label.covered_mask,
        )
    )
    nondominated_count = len(pruned)
    return (
        pruned[:max_labels],
        nondominated_count,
        nondominated_count > max_labels,
    )


def find_best_single_officer_route(
    scenario: PlanningScenario,
    shift: int,
    uncovered_incidents: List[PlanningIncident],
    max_labels: int,
) -> SingleOfficerRoute:
    shift_start = shift * scenario.periods_per_shift
    shift_end = shift_start + scenario.periods_per_shift
    incidents = sorted(
        (
            incident
            for incident in uncovered_incidents
            if shift_start <= incident.period < shift_end
        ),
        key=lambda incident: (incident.period, incident.request_id),
    )
    if not incidents:
        return SingleOfficerRoute(shift=shift, visits=(), covered_request_ids=())

    index_by_request = {
        incident.request_id: index for index, incident in enumerate(incidents)
    }
    candidate_masks = _candidate_masks(scenario, incidents, index_by_request)
    labels: List[_Label] = []
    search_was_truncated = False
    peak_nondominated_labels = 0

    for period in sorted(candidate_masks):
        next_labels: List[_Label] = list(labels)
        for region_id, immediate_mask in candidate_masks[period].items():
            visit = PatrolVisit(period=period, region_id=region_id)
            next_labels.append(
                _Label(
                    last_period=period,
                    last_region_id=region_id,
                    covered_mask=immediate_mask,
                    visits=(visit,),
                )
            )
            for label in labels:
                travel = scenario.travel_periods[(label.last_region_id, region_id)]
                if label.last_period + travel + 1 > period:
                    continue
                next_labels.append(
                    _Label(
                        last_period=period,
                        last_region_id=region_id,
                        covered_mask=label.covered_mask | immediate_mask,
                        visits=label.visits + (visit,),
                    )
                )
        labels, nondominated_count, truncated = _prune_labels(
            next_labels,
            max_labels,
        )
        peak_nondominated_labels = max(
            peak_nondominated_labels,
            nondominated_count,
        )
        search_was_truncated = search_was_truncated or truncated

    if not labels:
        return SingleOfficerRoute(shift=shift, visits=(), covered_request_ids=())

    best = min(
        labels,
        key=lambda label: (
            -_count_bits(label.covered_mask),
            len(label.visits),
            label.last_period,
            label.last_region_id,
        ),
    )
    covered_request_ids = tuple(
        incident.request_id
        for index, incident in enumerate(incidents)
        if best.covered_mask & (1 << index)
    )
    return SingleOfficerRoute(
        shift=shift,
        visits=best.visits,
        covered_request_ids=covered_request_ids,
        search_was_truncated=search_was_truncated,
        peak_nondominated_labels=peak_nondominated_labels,
    )
