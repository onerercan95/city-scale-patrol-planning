from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/patrol-planning-matplotlib")

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

from patrol_planning.domain.models import PlanningScenario
from patrol_planning.visualization.vfop_layers import aggregate_vfop


def build_vfop_summary(
    scenario: PlanningScenario,
    output_path: Path,
) -> None:
    rows = int(scenario.metadata["grid_rows"])
    columns = int(scenario.metadata["grid_columns"])
    views = [
        ("Full day", list(range(scenario.periods))),
        *[
            (
                f"Shift {shift}",
                list(
                    range(
                        shift * scenario.periods_per_shift,
                        (shift + 1) * scenario.periods_per_shift,
                    )
                ),
            )
            for shift in range(scenario.shifts_per_day)
        ],
    ]
    aggregated = [
        (title, aggregate_vfop(scenario, periods))
        for title, periods in views
    ]
    common_minimum = min(min(values.values()) for _, values in aggregated)
    common_maximum = max(max(values.values()) for _, values in aggregated)

    sns.set_theme(style="white", context="talk")
    figure, axes = plt.subplots(2, 2, figsize=(15, 12))
    for axis, (title, values) in zip(axes.flat, aggregated):
        matrix = np.zeros((rows, columns))
        for region in scenario.regions:
            matrix[rows - 1 - region.row, region.column] = values[region.region_id]
        sns.heatmap(
            matrix,
            cmap="YlOrRd",
            vmin=common_minimum,
            vmax=common_maximum,
            square=True,
            cbar_kws={"label": "Mean VFoP"},
            ax=axis,
        )
        axis.set_title(title, fontweight="bold")
        axis.set_xlabel("Grid column")
        axis.set_ylabel("Grid row")

    figure.suptitle(
        "Central LA Visibility Demand by Patrol Shift",
        fontsize=23,
        fontweight="bold",
    )
    figure.tight_layout(rect=(0, 0, 1, 0.96))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=180)
    plt.close(figure)
