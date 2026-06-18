from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from patrol_planning.domain.routes import GraftingResult
from patrol_planning.output.layout import data_directory
from patrol_planning.validation.grafting import GraftingValidationReport


def export_grafting_result(
    result: GraftingResult,
    validation: GraftingValidationReport,
    output_directory: Path,
) -> None:
    output_directory = data_directory(output_directory)
    with (output_directory / "grafting_result.json").open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(result.to_dict(), handle, indent=2)
    with (output_directory / "grafting_validation_report.json").open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(validation.to_dict(), handle, indent=2)

    rows = [
        {
            "officer_id": officer_id,
            "period": visit.period,
            "region_id": visit.region_id,
        }
        for officer_id, visits in sorted(result.added_visits.items())
        for visit in visits
    ]
    pd.DataFrame(
        rows,
        columns=["officer_id", "period", "region_id"],
    ).to_csv(output_directory / "grafted_visits.csv", index=False)
