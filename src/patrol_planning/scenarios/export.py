from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import List

import pandas as pd

from patrol_planning.demand.poisson import PoissonRate
from patrol_planning.domain.models import PlanningScenario
from patrol_planning.output.layout import data_directory
from patrol_planning.validation.reports import DataValidationReport
from patrol_planning.validation.scenario import ScenarioValidationReport


def export_scenario(
    scenario: PlanningScenario,
    report: DataValidationReport,
    scenario_report: ScenarioValidationReport,
    output_directory: Path,
) -> None:
    output_directory = data_directory(output_directory)

    with (output_directory / "scenario.json").open("w", encoding="utf-8") as handle:
        json.dump(scenario.to_dict(), handle, indent=2)
    with (output_directory / "validation_report.json").open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(report.to_dict(), handle, indent=2)
    with (output_directory / "scenario_validation_report.json").open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(scenario_report.to_dict(), handle, indent=2)

    pd.DataFrame([incident.__dict__ for incident in scenario.incidents]).to_csv(
        output_directory / "planning_incidents.csv",
        index=False,
    )
    pd.DataFrame([region.__dict__ for region in scenario.regions]).to_csv(
        output_directory / "regions.csv",
        index=False,
    )


def export_poisson_rates(
    rates: List[PoissonRate],
    output_directory: Path,
) -> None:
    if not rates:
        return
    output_directory = data_directory(output_directory)
    pd.DataFrame([asdict(rate) for rate in rates]).to_csv(
        output_directory / "poisson_rates.csv",
        index=False,
    )
