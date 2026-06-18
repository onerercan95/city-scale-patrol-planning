from patrol_planning.domain.models import GridRegion, PlanningScenario
from patrol_planning.domain.routes import MinPResult
from patrol_planning.solvers.maxp.allocation import solve_maxp
from patrol_planning.solvers.maxp.flow import solve_fixed_shift
from patrol_planning.validation.maxp import validate_maxp_result


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


def test_fixed_shift_flow_reproduces_figure_three_optimum() -> None:
    regions = [_region(0), _region(1), _region(2)]
    infeasible = 99
    travel = {
        (source.region_id, target.region_id): infeasible
        for source in regions
        for target in regions
    }
    for edge in [(0, 0), (0, 1), (1, 1), (2, 1), (2, 2)]:
        travel[edge] = 0
    values = {
        (0, 0): 9.0,
        (0, 1): 1.0,
        (0, 2): 6.0,
        (1, 0): 4.0,
        (1, 1): 8.0,
        (1, 2): 1.0,
    }
    scenario = PlanningScenario(
        name="figure-3",
        periods=2,
        shifts_per_day=1,
        periods_per_shift=2,
        officers=[1, 2],
        regions=regions,
        incidents=[],
        vfop=values,
        travel_periods=travel,
        metadata={},
    )

    result = solve_fixed_shift(scenario, shift=0, officer_count=2, cost_scale=100)

    assert result.pvr == 27.0
    assert {
        tuple((visit.period, visit.region_id) for visit in route)
        for route in result.routes
    } == {
        ((0, 0), (1, 0)),
        ((0, 2), (1, 1)),
    }


def test_shift_allocation_uses_all_remaining_officers() -> None:
    regions = [_region(0), _region(1)]
    scenario = PlanningScenario(
        name="allocation",
        periods=3,
        shifts_per_day=3,
        periods_per_shift=1,
        officers=[1, 2],
        regions=regions,
        incidents=[],
        vfop={
            (0, 0): 1.0,
            (0, 1): 0.9,
            (1, 0): 0.2,
            (1, 1): 0.1,
            (2, 0): 0.1,
            (2, 1): 0.05,
        },
        travel_periods={
            (source.region_id, target.region_id): 0
            for source in regions
            for target in regions
        },
        metadata={},
    )
    minp = MinPResult(
        feasible=True,
        routes=[],
        coverage=[],
        uncovered_request_ids=[],
        available_officers=2,
        algorithm="none",
    )

    result = solve_maxp(scenario, minp, cost_scale=100, random_seed=1)
    report = validate_maxp_result(scenario, minp, result)

    assert result.shift_allocation == {0: 2, 1: 0, 2: 0}
    assert result.maxp_pvr == 1.9
    assert report.valid
