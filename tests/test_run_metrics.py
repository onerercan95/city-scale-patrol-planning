from pathlib import Path

from patrol_planning.domain.models import GridRegion, PlanningIncident, PlanningScenario
from patrol_planning.domain.routes import (
    GraftingResult,
    IncidentCoverage,
    MaxPResult,
    MinPResult,
    OfficerRoute,
    PatrolVisit,
)
from patrol_planning.validation.grafting import GraftingValidationReport
from patrol_planning.validation.minp import MinPValidationReport
from patrol_planning.visualization.run_metrics import build_run_metric_images


def test_run_metric_images_are_created(tmp_path: Path) -> None:
    regions = [
        GridRegion(0, 0, 0, 34.0, -118.0, 33.9, 34.1, -118.1, -117.9),
        GridRegion(1, 0, 1, 34.0, -117.9, 33.9, 34.1, -117.9, -117.8),
    ]
    incident = PlanningIncident(
        "IR-1",
        1,
        0,
        0,
        "urgent",
        1,
        34.0,
        -118.0,
    )
    scenario = PlanningScenario(
        name="metric-test",
        periods=2,
        shifts_per_day=1,
        periods_per_shift=2,
        officers=[1, 2],
        regions=regions,
        incidents=[incident],
        vfop={(0, 0): 0.2, (0, 1): 0.8, (1, 0): 0.3, (1, 1): 0.9},
        travel_periods={(a.region_id, b.region_id): 1 for a in regions for b in regions},
        metadata={"grid_rows": 1, "grid_columns": 2},
    )
    minp_route = OfficerRoute(
        officer_id=1,
        shift=0,
        visits=[PatrolVisit(0, 0)],
        covered_request_ids=["IR-1"],
    )
    coverage = IncidentCoverage("IR-1", 1, 0, 0, 0, 0, 0, 1)
    minp = MinPResult(
        feasible=True,
        routes=[minp_route],
        coverage=[coverage],
        uncovered_request_ids=[],
        available_officers=2,
        algorithm="test",
    )
    maxp = MaxPResult(
        routes=[
            OfficerRoute(
                officer_id=2,
                shift=0,
                visits=[PatrolVisit(0, 1)],
                covered_request_ids=[],
            )
        ],
        remaining_officer_ids=[2],
        shift_allocation={0: 1},
        maxp_pvr=0.8,
        minp_pvr=0.2,
        combined_pvr=1.0,
        alpha=0.5,
        approximation_bound=0.5,
        algorithm="test",
    )
    grafting = GraftingResult(
        grafted_minp_routes=[
            OfficerRoute(
                officer_id=1,
                shift=0,
                visits=[PatrolVisit(0, 0), PatrolVisit(1, 1)],
                covered_request_ids=["IR-1"],
            )
        ],
        added_visits={1: [PatrolVisit(1, 1)]},
        baseline_combined_pvr=1.0,
        grafted_combined_pvr=1.9,
        grafting_gain=0.9,
        processed_window_count=1,
        productive_window_count=1,
        algorithm="test",
    )
    minp_report = MinPValidationReport(
        valid=True,
        feasible=True,
        covered_request_count=1,
        uncovered_request_count=0,
        selected_officer_count=1,
    )
    grafting_report = GraftingValidationReport(
        valid=True,
        incident_coverage_preserved=True,
        required_visits_preserved=True,
        added_visit_count=1,
        baseline_combined_pvr=1.0,
        grafted_combined_pvr=1.9,
        grafting_gain=0.9,
    )

    build_run_metric_images(
        scenario,
        minp,
        maxp,
        grafting,
        minp_report,
        grafting_report,
        {"minp": 0.1, "maxp": 0.2, "grafting": 0.05},
        tmp_path,
    )

    expected = {
        "run_summary.png",
        "pvr_stage_comparison.png",
        "officer_allocation.png",
        "incident_coverage_summary.png",
        "grafting_summary.png",
    }
    assert {path.name for path in tmp_path.glob("*.png")} == expected
    assert all((tmp_path / name).stat().st_size > 0 for name in expected)
