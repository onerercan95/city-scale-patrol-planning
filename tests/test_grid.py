from datetime import datetime

from patrol_planning.domain.models import HistoricalIncident
from patrol_planning.geography.grid import build_grid


def incident(source_id: int, latitude: float, longitude: float) -> HistoricalIncident:
    return HistoricalIncident(
        source_id=source_id,
        occurred_at=datetime(2023, 1, 1, 12, 0),
        latitude=latitude,
        longitude=longitude,
        incident_type="ROBBERY",
        area_name="Central",
    )


def test_grid_assigns_boundary_points_safely() -> None:
    grid = build_grid(
        [
            incident(1, 34.0, -118.3),
            incident(2, 34.2, -118.1),
        ],
        rows=2,
        columns=2,
    )

    assert len(grid.regions) == 4
    assert grid.region_id_for(34.0, -118.3) == 0
    assert grid.region_id_for(34.2, -118.1) == 3
