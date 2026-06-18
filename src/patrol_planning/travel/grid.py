from typing import Dict, List, Tuple

from patrol_planning.domain.models import GridRegion


def build_grid_travel_matrix(
    regions: List[GridRegion],
    periods_per_grid_step: int,
) -> Dict[Tuple[int, int], int]:
    return {
        (source.region_id, target.region_id): (
            abs(source.row - target.row) + abs(source.column - target.column)
        )
        * periods_per_grid_step
        for source in regions
        for target in regions
    }
