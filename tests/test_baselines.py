from patrol_planning.baselines.greedy_visibility import solve_greedy_visibility
from patrol_planning.baselines.static_checkpoints import solve_static_checkpoints
from patrol_planning.domain.models import GridRegion, PlanningIncident, PlanningScenario
from patrol_planning.evaluation.pvr import calculate_pvr
from patrol_planning.evaluation.routes import covered_incident_ids, routes_are_feasible


def _region(region_id: int) -> GridRegion:
    return GridRegion(
        region_id=region_id,
        row=region_id,
        column=0,
        center_latitude=34.0 + region_id * 0.01,
        center_longitude=-118.0,
        min_latitude=34.0,
        max_latitude=34.01,
        min_longitude=-118.0,
        max_longitude=-117.99,
    )


def test_greedy_visibility_reproduces_figure_three_greedy_value() -> None:
    regions = [_region(0), _region(1), _region(2)]
    travel = {
        (source.region_id, target.region_id): 99
        for source in regions
        for target in regions
    }
    for edge in [(0, 0), (0, 1), (1, 1), (2, 1), (2, 2)]:
        travel[edge] = 0
    scenario = PlanningScenario(
        name="figure-3-greedy",
        periods=2,
        shifts_per_day=1,
        periods_per_shift=2,
        officers=[1, 2],
        regions=regions,
        incidents=[],
        vfop={
            (0, 0): 9.0,
            (0, 1): 1.0,
            (0, 2): 6.0,
            (1, 0): 4.0,
            (1, 1): 8.0,
            (1, 2): 1.0,
        },
        travel_periods=travel,
        metadata={},
    )

    routes = solve_greedy_visibility(scenario)

    assert calculate_pvr(scenario, routes) == 24.0
    assert routes_are_feasible(scenario, routes)


def test_static_checkpoints_measure_incident_coverage() -> None:
    regions = [_region(0), _region(1)]
    scenario = PlanningScenario(
        name="static",
        periods=2,
        shifts_per_day=1,
        periods_per_shift=2,
        officers=[1],
        regions=regions,
        incidents=[
            PlanningIncident("IR-1", 1, 0, 0, "urgent", 0, 34.0, -118.0)
        ],
        vfop={(0, 0): 1.0, (1, 0): 1.0, (0, 1): 0.1, (1, 1): 0.1},
        travel_periods={
            (source.region_id, target.region_id): abs(
                source.region_id - target.region_id
            )
            for source in regions
            for target in regions
        },
        metadata={},
    )

    routes = solve_static_checkpoints(scenario)

    assert covered_incident_ids(scenario, routes) == {"IR-1"}
    assert routes_are_feasible(scenario, routes)
