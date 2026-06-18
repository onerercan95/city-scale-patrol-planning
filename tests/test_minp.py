from patrol_planning.domain.models import GridRegion, PlanningIncident, PlanningScenario
from patrol_planning.domain.routes import MinPResult, OfficerRoute, PatrolVisit
from patrol_planning.solvers.minp.greedy import solve_minp
from patrol_planning.solvers.minp.single_officer import find_best_single_officer_route
from patrol_planning.validation.minp import validate_minp_result


def _region(region_id: int, row: int, column: int) -> GridRegion:
    return GridRegion(
        region_id=region_id,
        row=row,
        column=column,
        center_latitude=34.0 + row * 0.01,
        center_longitude=-118.0 + column * 0.01,
        min_latitude=34.0,
        max_latitude=34.01,
        min_longitude=-118.0,
        max_longitude=-117.99,
    )


def _scenario() -> PlanningScenario:
    regions = [_region(0, 0, 0), _region(1, 0, 1), _region(2, 1, 0)]
    travel = {
        (source.region_id, target.region_id): abs(source.row - target.row)
        + abs(source.column - target.column)
        for source in regions
        for target in regions
    }
    incidents = [
        PlanningIncident("IR-1", 1, 1, 0, "urgent", 0, 34.0, -118.0),
        PlanningIncident("IR-2", 2, 1, 0, "urgent", 0, 34.0, -118.0),
        PlanningIncident("IR-3", 3, 3, 1, "urgent", 0, 34.0, -117.99),
    ]
    return PlanningScenario(
        name="small",
        periods=8,
        shifts_per_day=1,
        periods_per_shift=8,
        officers=[1, 2],
        regions=regions,
        incidents=incidents,
        vfop={(period, region.region_id): 0.1 for period in range(8) for region in regions},
        travel_periods=travel,
        metadata={},
    )


def test_single_officer_dp_covers_simultaneous_incidents_and_moves() -> None:
    scenario = _scenario()

    route = find_best_single_officer_route(
        scenario,
        shift=0,
        uncovered_incidents=scenario.incidents,
        max_labels=500,
    )

    assert route.coverage_count == 3
    assert list(route.visits) == [
        PatrolVisit(period=1, region_id=0),
        PatrolVisit(period=3, region_id=1),
    ]
    assert not route.search_was_truncated


def test_single_officer_dp_reports_when_label_cap_binds() -> None:
    scenario = _scenario()

    route = find_best_single_officer_route(
        scenario,
        shift=0,
        uncovered_incidents=scenario.incidents,
        max_labels=1,
    )

    assert route.search_was_truncated
    assert route.peak_nondominated_labels > 1


def test_greedy_minp_result_passes_independent_validation() -> None:
    scenario = _scenario()

    result = solve_minp(scenario, max_labels=500)
    report = validate_minp_result(scenario, result)

    assert result.feasible
    assert result.selected_officer_count == 1
    assert report.valid
    assert report.covered_request_count == 3


def test_validator_rejects_impossible_movement() -> None:
    scenario = _scenario()
    result = MinPResult(
        feasible=True,
        routes=[
            OfficerRoute(
                officer_id=1,
                shift=0,
                visits=[
                    PatrolVisit(period=1, region_id=0),
                    PatrolVisit(period=2, region_id=1),
                ],
                covered_request_ids=["IR-1", "IR-2", "IR-3"],
            )
        ],
        coverage=[],
        uncovered_request_ids=[],
        available_officers=2,
        algorithm="invalid test route",
    )

    report = validate_minp_result(scenario, result)

    assert not report.valid
    assert any("cannot move" in error for error in report.errors)
