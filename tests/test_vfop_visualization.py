import pytest

from patrol_planning.domain.models import GridRegion, PlanningScenario
from patrol_planning.domain.routes import MaxPResult, OfficerRoute, PatrolVisit
from patrol_planning.visualization.maxp_map import build_maxp_map
from patrol_planning.visualization.vfop_layers import aggregate_vfop, vfop_color


def test_vfop_aggregation_and_color_scale() -> None:
    regions = [
        GridRegion(0, 0, 0, 34.0, -118.0, 33.9, 34.1, -118.1, -117.9),
        GridRegion(1, 0, 1, 34.0, -117.9, 33.9, 34.1, -117.9, -117.8),
    ]
    scenario = PlanningScenario(
        name="vfop",
        periods=2,
        shifts_per_day=1,
        periods_per_shift=2,
        officers=[1],
        regions=regions,
        incidents=[],
        vfop={(0, 0): 0.2, (1, 0): 0.4, (0, 1): 0.8, (1, 1): 1.0},
        travel_periods={(a.region_id, b.region_id): 0 for a in regions for b in regions},
        metadata={"grid_rows": 1, "grid_columns": 2},
    )

    values = aggregate_vfop(scenario, [0, 1])

    assert values[0] == pytest.approx(0.3)
    assert values[1] == pytest.approx(0.9)
    assert vfop_color(0.0) != vfop_color(1.0)


def test_maxp_map_contains_only_maxp_route_label(tmp_path) -> None:
    regions = [
        GridRegion(0, 0, 0, 34.0, -118.0, 33.9, 34.1, -118.1, -117.9),
        GridRegion(1, 0, 1, 34.0, -117.9, 33.9, 34.1, -117.9, -117.8),
    ]
    scenario = PlanningScenario(
        name="maxp-map",
        periods=2,
        shifts_per_day=1,
        periods_per_shift=2,
        officers=[1],
        regions=regions,
        incidents=[],
        vfop={(0, 0): 0.2, (1, 0): 0.4, (0, 1): 0.8, (1, 1): 1.0},
        travel_periods={(a.region_id, b.region_id): 1 for a in regions for b in regions},
        metadata={"grid_rows": 1, "grid_columns": 2},
    )
    result = MaxPResult(
        remaining_officer_ids=[1],
        shift_allocation={0: 1},
        routes=[
            OfficerRoute(
                officer_id=1,
                shift=0,
                visits=[PatrolVisit(period=0, region_id=0), PatrolVisit(period=1, region_id=1)],
                covered_request_ids=[],
            )
        ],
        maxp_pvr=1.0,
        minp_pvr=0.0,
        combined_pvr=1.0,
        alpha=0.0,
        approximation_bound=1.0,
        algorithm="test",
    )
    output = tmp_path / "maxp_routes_map.html"

    build_maxp_map(scenario, result, output)

    html = output.read_text(encoding="utf-8")
    assert "MaxP visibility routes" in html
    assert "MaxP officer 1" in html
    assert "MinP officer" not in html
