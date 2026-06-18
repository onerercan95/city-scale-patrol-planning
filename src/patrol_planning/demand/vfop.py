from collections import Counter
from typing import Dict, List, Tuple

from patrol_planning.domain.models import HistoricalIncident
from patrol_planning.geography.grid import Grid
from patrol_planning.time.periods import period_for_datetime


def estimate_vfop(
    incidents: List[HistoricalIncident],
    grid: Grid,
    periods: int,
    period_minutes: int,
    baseline: float,
) -> Dict[Tuple[int, int], float]:
    counts = Counter(
        (
            period_for_datetime(incident.occurred_at, period_minutes),
            grid.region_id_for(incident.latitude, incident.longitude),
        )
        for incident in incidents
    )
    maximum = max(counts.values(), default=1)
    vfop: Dict[Tuple[int, int], float] = {}

    for period in range(periods):
        for region in grid.regions:
            normalized_count = counts[(period, region.region_id)] / maximum
            vfop[(period, region.region_id)] = round(
                baseline + (1.0 - baseline) * normalized_count,
                6,
            )
    return vfop
