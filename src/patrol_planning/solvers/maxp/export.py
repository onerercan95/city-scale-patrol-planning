from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from patrol_planning.domain.routes import MaxPResult
from patrol_planning.output.layout import data_directory
from patrol_planning.validation.maxp import MaxPValidationReport


def export_maxp_result(
    result: MaxPResult,
    validation: MaxPValidationReport,
    output_directory: Path,
) -> None:
    output_directory = data_directory(output_directory)
    with (output_directory / "maxp_result.json").open("w", encoding="utf-8") as handle:
        json.dump(result.to_dict(), handle, indent=2)
    with (output_directory / "maxp_validation_report.json").open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(validation.to_dict(), handle, indent=2)

    rows = [
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
        rows,
        columns=["officer_id", "shift", "period", "region_id"],
    ).to_csv(output_directory / "maxp_routes.csv", index=False)
