from __future__ import annotations

from dataclasses import dataclass
from math import floor
from typing import List

from patrol_planning.domain.models import GridRegion, HistoricalIncident


@dataclass(frozen=True)
class Grid:
    rows: int
    columns: int
    min_latitude: float
    max_latitude: float
    min_longitude: float
    max_longitude: float
    regions: List[GridRegion]

    @property
    def latitude_step(self) -> float:
        return (self.max_latitude - self.min_latitude) / self.rows

    @property
    def longitude_step(self) -> float:
        return (self.max_longitude - self.min_longitude) / self.columns

    def region_id_for(self, latitude: float, longitude: float) -> int:
        row = floor((latitude - self.min_latitude) / self.latitude_step)
        column = floor((longitude - self.min_longitude) / self.longitude_step)
        row = min(max(row, 0), self.rows - 1)
        column = min(max(column, 0), self.columns - 1)
        return row * self.columns + column


def build_grid(
    incidents: List[HistoricalIncident],
    rows: int,
    columns: int,
) -> Grid:
    if not incidents:
        raise ValueError("Cannot build a grid without incidents")

    min_latitude = min(incident.latitude for incident in incidents)
    max_latitude = max(incident.latitude for incident in incidents)
    min_longitude = min(incident.longitude for incident in incidents)
    max_longitude = max(incident.longitude for incident in incidents)

    if min_latitude == max_latitude or min_longitude == max_longitude:
        raise ValueError("Incident coordinates do not span a two-dimensional area")

    latitude_step = (max_latitude - min_latitude) / rows
    longitude_step = (max_longitude - min_longitude) / columns
    regions: List[GridRegion] = []

    for row in range(rows):
        for column in range(columns):
            region_min_latitude = min_latitude + row * latitude_step
            region_max_latitude = region_min_latitude + latitude_step
            region_min_longitude = min_longitude + column * longitude_step
            region_max_longitude = region_min_longitude + longitude_step
            regions.append(
                GridRegion(
                    region_id=row * columns + column,
                    row=row,
                    column=column,
                    center_latitude=(region_min_latitude + region_max_latitude) / 2,
                    center_longitude=(region_min_longitude + region_max_longitude) / 2,
                    min_latitude=region_min_latitude,
                    max_latitude=region_max_latitude,
                    min_longitude=region_min_longitude,
                    max_longitude=region_max_longitude,
                )
            )

    return Grid(
        rows=rows,
        columns=columns,
        min_latitude=min_latitude,
        max_latitude=max_latitude,
        min_longitude=min_longitude,
        max_longitude=max_longitude,
        regions=regions,
    )
