from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class PatrolVisit:
    period: int
    region_id: int


@dataclass
class OfficerRoute:
    officer_id: int
    shift: int
    visits: List[PatrolVisit]
    covered_request_ids: List[str]


@dataclass(frozen=True)
class IncidentCoverage:
    request_id: str
    officer_id: int
    shift: int
    officer_region_id: int
    incident_region_id: int
    period: int
    travel_periods: int
    response_limit_periods: int


@dataclass
class MinPResult:
    feasible: bool
    routes: List[OfficerRoute]
    coverage: List[IncidentCoverage]
    uncovered_request_ids: List[str]
    available_officers: int
    algorithm: str
    label_cap: Optional[int] = None
    search_truncated: bool = False
    truncated_search_count: int = 0
    peak_nondominated_labels: int = 0

    @property
    def selected_officer_count(self) -> int:
        return len(self.routes)

    def to_dict(self) -> Dict[str, object]:
        return {
            "feasible": self.feasible,
            "selected_officer_count": self.selected_officer_count,
            "available_officers": self.available_officers,
            "algorithm": self.algorithm,
            "label_cap": self.label_cap,
            "search_truncated": self.search_truncated,
            "truncated_search_count": self.truncated_search_count,
            "peak_nondominated_labels": self.peak_nondominated_labels,
            "routes": [
                {
                    "officer_id": route.officer_id,
                    "shift": route.shift,
                    "visits": [asdict(visit) for visit in route.visits],
                    "covered_request_ids": route.covered_request_ids,
                }
                for route in self.routes
            ],
            "coverage": [asdict(coverage) for coverage in self.coverage],
            "uncovered_request_ids": self.uncovered_request_ids,
        }


@dataclass
class MaxPResult:
    routes: List[OfficerRoute]
    remaining_officer_ids: List[int]
    shift_allocation: Dict[int, int]
    maxp_pvr: float
    minp_pvr: float
    combined_pvr: float
    alpha: float
    approximation_bound: float
    algorithm: str

    @property
    def assigned_officer_count(self) -> int:
        return len(self.routes)

    def to_dict(self) -> Dict[str, object]:
        return {
            "assigned_officer_count": self.assigned_officer_count,
            "remaining_officer_ids": self.remaining_officer_ids,
            "shift_allocation": {
                str(shift): count for shift, count in sorted(self.shift_allocation.items())
            },
            "maxp_pvr": self.maxp_pvr,
            "minp_pvr": self.minp_pvr,
            "combined_pvr": self.combined_pvr,
            "alpha": self.alpha,
            "approximation_bound": self.approximation_bound,
            "algorithm": self.algorithm,
            "routes": [
                {
                    "officer_id": route.officer_id,
                    "shift": route.shift,
                    "visits": [asdict(visit) for visit in route.visits],
                    "covered_request_ids": route.covered_request_ids,
                }
                for route in self.routes
            ],
        }


@dataclass
class GraftingResult:
    grafted_minp_routes: List[OfficerRoute]
    added_visits: Dict[int, List[PatrolVisit]]
    baseline_combined_pvr: float
    grafted_combined_pvr: float
    grafting_gain: float
    processed_window_count: int
    productive_window_count: int
    algorithm: str

    @property
    def added_visit_count(self) -> int:
        return sum(len(visits) for visits in self.added_visits.values())

    def to_dict(self) -> Dict[str, object]:
        return {
            "baseline_combined_pvr": self.baseline_combined_pvr,
            "grafted_combined_pvr": self.grafted_combined_pvr,
            "grafting_gain": self.grafting_gain,
            "processed_window_count": self.processed_window_count,
            "productive_window_count": self.productive_window_count,
            "added_visit_count": self.added_visit_count,
            "algorithm": self.algorithm,
            "added_visits": {
                str(officer_id): [asdict(visit) for visit in visits]
                for officer_id, visits in sorted(self.added_visits.items())
            },
            "grafted_minp_routes": [
                {
                    "officer_id": route.officer_id,
                    "shift": route.shift,
                    "visits": [asdict(visit) for visit in route.visits],
                    "covered_request_ids": route.covered_request_ids,
                }
                for route in self.grafted_minp_routes
            ],
        }
