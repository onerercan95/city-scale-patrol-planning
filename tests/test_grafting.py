from patrol_planning.domain.models import GridRegion, PlanningIncident, PlanningScenario
from patrol_planning.domain.routes import (
    IncidentCoverage,
    MaxPResult,
    MinPResult,
    OfficerRoute,
    PatrolVisit,
)
from patrol_planning.solvers.grafting.dp import solve_grafting
from patrol_planning.validation.grafting import validate_grafting_result


def _region(region_id: int, column: int) -> GridRegion:
    return GridRegion(
        region_id=region_id,
        row=0,
        column=column,
        center_latitude=34.0,
        center_longitude=-118.0 + column * 0.01,
        min_latitude=34.0,
        max_latitude=34.01,
        min_longitude=-118.0,
        max_longitude=-117.99,
    )


def test_grafting_adds_marginal_visibility_and_preserves_coverage() -> None:
    regions = [_region(0, 0), _region(1, 1), _region(2, 2)]
    travel = {
        (source.region_id, target.region_id): abs(source.column - target.column)
        for source in regions
        for target in regions
    }
    scenario = PlanningScenario(
        name="graft",
        periods=6,
        shifts_per_day=1,
        periods_per_shift=6,
        officers=[1, 2],
        regions=regions,
        incidents=[
            PlanningIncident("IR-1", 1, 0, 0, "urgent", 0, 34.0, -118.0),
            PlanningIncident("IR-2", 2, 5, 0, "urgent", 0, 34.0, -118.0),
        ],
        vfop={
            (period, region.region_id): (
                1.0 if (period, region.region_id) == (2, 1) else 0.1
            )
            for period in range(6)
            for region in regions
        },
        travel_periods=travel,
        metadata={},
    )
    minp = MinPResult(
        feasible=True,
        routes=[
            OfficerRoute(
                officer_id=1,
                shift=0,
                visits=[PatrolVisit(0, 0), PatrolVisit(5, 0)],
                covered_request_ids=["IR-1", "IR-2"],
            )
        ],
        coverage=[
            IncidentCoverage("IR-1", 1, 0, 0, 0, 0, 0, 0),
            IncidentCoverage("IR-2", 1, 0, 0, 0, 5, 0, 0),
        ],
        uncovered_request_ids=[],
        available_officers=2,
        algorithm="test",
    )
    maxp = MaxPResult(
        routes=[
            OfficerRoute(
                officer_id=2,
                shift=0,
                visits=[PatrolVisit(1, 2)],
                covered_request_ids=[],
            )
        ],
        remaining_officer_ids=[2],
        shift_allocation={0: 1},
        maxp_pvr=0.1,
        minp_pvr=0.2,
        combined_pvr=0.3,
        alpha=0.5,
        approximation_bound=0.5,
        algorithm="test",
    )

    result = solve_grafting(scenario, minp, maxp)
    report = validate_grafting_result(scenario, minp, maxp, result)

    assert PatrolVisit(2, 1) in result.added_visits[1]
    assert result.grafting_gain >= 1.0
    assert report.valid
    assert report.incident_coverage_preserved
