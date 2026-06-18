from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import List

import numpy as np

from patrol_planning.demand.classification import (
    classify_incident,
    response_limit_for_category,
)
from patrol_planning.domain.models import HistoricalIncident, PlanningIncident
from patrol_planning.geography.grid import Grid
from patrol_planning.time.periods import period_for_datetime


@dataclass(frozen=True)
class PoissonRate:
    category: str
    period: int
    region_id: int
    historical_count: int
    history_days: int
    daily_rate: float


def learn_poisson_rates(
    incidents: List[HistoricalIncident],
    grid: Grid,
    history_days: int,
    period_minutes: int,
) -> List[PoissonRate]:
    if history_days <= 0:
        raise ValueError("history_days must be positive")

    bucket_counts = Counter()
    for incident in incidents:
        classification = classify_incident(incident.incident_type)
        bucket_counts[
            (
                classification.category,
                period_for_datetime(incident.occurred_at, period_minutes),
                grid.region_id_for(incident.latitude, incident.longitude),
            )
        ] += 1

    return [
        PoissonRate(
            category=category,
            period=period,
            region_id=region_id,
            historical_count=count,
            history_days=history_days,
            daily_rate=count / history_days,
        )
        for (category, period, region_id), count in sorted(bucket_counts.items())
    ]


def sample_poisson_incidents(
    rates: List[PoissonRate],
    grid: Grid,
    random_seed: int,
    rate_scale: float = 1.0,
) -> List[PlanningIncident]:
    if rate_scale <= 0:
        raise ValueError("rate_scale must be positive")

    rng = np.random.default_rng(random_seed)
    planning_incidents: List[PlanningIncident] = []
    request_number = 1
    for rate in rates:
        sampled_count = int(rng.poisson(rate.daily_rate * rate_scale))
        region = grid.regions[rate.region_id]
        for _ in range(sampled_count):
            planning_incidents.append(
                PlanningIncident(
                    request_id=f"IR-{request_number:04d}",
                    source_id=-request_number,
                    period=rate.period,
                    region_id=rate.region_id,
                    category=rate.category,
                    response_limit_periods=response_limit_for_category(
                        rate.category
                    ),
                    latitude=region.center_latitude,
                    longitude=region.center_longitude,
                )
            )
            request_number += 1
    return planning_incidents
