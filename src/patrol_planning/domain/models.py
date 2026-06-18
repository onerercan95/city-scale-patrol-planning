from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class HistoricalIncident:
    source_id: int
    occurred_at: datetime
    latitude: float
    longitude: float
    incident_type: str
    area_name: str


@dataclass(frozen=True)
class GridRegion:
    region_id: int
    row: int
    column: int
    center_latitude: float
    center_longitude: float
    min_latitude: float
    max_latitude: float
    min_longitude: float
    max_longitude: float


@dataclass(frozen=True)
class PlanningIncident:
    request_id: str
    source_id: int
    period: int
    region_id: int
    category: str
    response_limit_periods: int
    latitude: float
    longitude: float


@dataclass
class PlanningScenario:
    name: str
    periods: int
    shifts_per_day: int
    periods_per_shift: int
    officers: List[int]
    regions: List[GridRegion]
    incidents: List[PlanningIncident]
    vfop: Dict[Tuple[int, int], float]
    travel_periods: Dict[Tuple[int, int], int]
    metadata: Dict[str, object]

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "periods": self.periods,
            "shifts_per_day": self.shifts_per_day,
            "periods_per_shift": self.periods_per_shift,
            "officers": self.officers,
            "regions": [asdict(region) for region in self.regions],
            "incidents": [asdict(incident) for incident in self.incidents],
            "vfop": [
                {"period": period, "region_id": region_id, "value": value}
                for (period, region_id), value in sorted(self.vfop.items())
            ],
            "travel_periods": [
                {
                    "from_region_id": source,
                    "to_region_id": target,
                    "periods": periods,
                }
                for (source, target), periods in sorted(self.travel_periods.items())
            ],
            "metadata": self.metadata,
        }
