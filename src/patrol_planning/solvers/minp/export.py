from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from patrol_planning.domain.routes import MinPResult
from patrol_planning.output.layout import data_directory
from patrol_planning.validation.minp import MinPValidationReport


def export_minp_result(
    result: MinPResult,
    validation: MinPValidationReport,
    output_directory: Path,
) -> None:
    output_directory = data_directory(output_directory)
    with (output_directory / "minp_result.json").open("w", encoding="utf-8") as handle:
        json.dump(result.to_dict(), handle, indent=2)
    with (output_directory / "minp_validation_report.json").open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(validation.to_dict(), handle, indent=2)

    route_rows = [
        {
            "officer_id": route.officer_id,
            "shift": route.shift,
            "period": visit.period,
            "region_id": visit.region_id,
        }
        for route in result.routes
        for visit in route.visits
    ]
    pd.DataFrame(
        route_rows,
        columns=["officer_id", "shift", "period", "region_id"],
    ).to_csv(output_directory / "minp_routes.csv", index=False)
    pd.DataFrame(
        [coverage.__dict__ for coverage in result.coverage],
        columns=[
            "request_id",
            "officer_id",
            "shift",
            "officer_region_id",
            "incident_region_id",
            "period",
            "travel_periods",
            "response_limit_periods",
        ],
    ).to_csv(output_directory / "minp_coverage.csv", index=False)
