from __future__ import annotations

import os
from collections import Counter
from pathlib import Path
from typing import Mapping

os.environ.setdefault("MPLCONFIGDIR", "/tmp/patrol-planning-matplotlib")

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from patrol_planning.domain.models import PlanningScenario
from patrol_planning.domain.routes import GraftingResult, MaxPResult, MinPResult
from patrol_planning.validation.grafting import GraftingValidationReport
from patrol_planning.validation.minp import MinPValidationReport


INK = "#1f2933"
MUTED = "#64748b"
PAPER = "#f7f3ea"
RED = "#b84a3a"
BLUE = "#315f7d"
GREEN = "#2f7d62"
GOLD = "#d39a2c"


def _save(figure: plt.Figure, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=180, bbox_inches="tight", facecolor=PAPER)
    plt.close(figure)


def _style_axis(axis: plt.Axes) -> None:
    axis.set_facecolor(PAPER)
    axis.spines[["top", "right"]].set_visible(False)
    axis.spines[["left", "bottom"]].set_color("#b8afa1")
    axis.tick_params(colors=INK)
    axis.grid(axis="y", color="#d9d1c4", linewidth=0.8, alpha=0.7)
    axis.set_axisbelow(True)


def build_run_summary(
    scenario: PlanningScenario,
    minp_result: MinPResult,
    maxp_result: MaxPResult,
    grafting_result: GraftingResult,
    minp_report: MinPValidationReport,
    grafting_report: GraftingValidationReport,
    stage_seconds: Mapping[str, float],
    output_path: Path,
) -> None:
    coverage_rate = (
        minp_report.covered_request_count / len(scenario.incidents)
        if scenario.incidents
        else 1.0
    )
    total_solver_seconds = sum(stage_seconds.values())
    cards = [
        ("INCIDENTS", f"{len(scenario.incidents)}", "planning requests", RED),
        (
            "COVERAGE",
            f"{coverage_rate:.0%}",
            f"{minp_report.covered_request_count} covered",
            GREEN,
        ),
        (
            "OFFICERS",
            f"{len(scenario.officers)}",
            f"{minp_result.selected_officer_count} MinP / "
            f"{maxp_result.assigned_officer_count} MaxP",
            BLUE,
        ),
        (
            "FINAL PVR",
            f"{grafting_result.grafted_combined_pvr:.3f}",
            f"+{grafting_result.grafting_gain:.3f} from grafting",
            GOLD,
        ),
        (
            "SOLVER TIME",
            f"{total_solver_seconds:.3f}s",
            "MinP + MaxP + grafting",
            "#7c5b8f",
        ),
        (
            "VALIDATION",
            "PASSED" if grafting_report.valid else "FAILED",
            "coverage preserved"
            if grafting_report.incident_coverage_preserved
            else "coverage not preserved",
            GREEN if grafting_report.valid else RED,
        ),
    ]

    figure, axes = plt.subplots(2, 3, figsize=(15, 7.6), facecolor=PAPER)
    for axis, (heading, value, detail, color) in zip(axes.flat, cards):
        axis.set_facecolor("white")
        axis.set_xticks([])
        axis.set_yticks([])
        for spine in axis.spines.values():
            spine.set_color(color)
            spine.set_linewidth(2.2)
        axis.text(
            0.07,
            0.78,
            heading,
            transform=axis.transAxes,
            color=color,
            fontsize=12,
            fontweight="bold",
        )
        axis.text(
            0.07,
            0.42,
            value,
            transform=axis.transAxes,
            color=INK,
            fontsize=27,
            fontweight="bold",
        )
        axis.text(
            0.07,
            0.16,
            detail,
            transform=axis.transAxes,
            color=MUTED,
            fontsize=11,
        )

    figure.suptitle(
        f"Patrol Planning Run Summary: {scenario.name}",
        fontsize=22,
        color=INK,
        fontweight="bold",
    )
    figure.text(
        0.5,
        0.02,
        "Offline plan generated from historical demand and independently validated.",
        ha="center",
        color=MUTED,
        fontsize=11,
    )
    figure.tight_layout(rect=(0.02, 0.06, 0.98, 0.91), h_pad=1.5, w_pad=1.5)
    _save(figure, output_path)


def build_pvr_stage_comparison(
    maxp_result: MaxPResult,
    grafting_result: GraftingResult,
    output_path: Path,
) -> None:
    labels = ["MinP", "MinP + MaxP", "After grafting"]
    values = [
        maxp_result.minp_pvr,
        maxp_result.combined_pvr,
        grafting_result.grafted_combined_pvr,
    ]
    colors = [RED, BLUE, GREEN]

    figure, axis = plt.subplots(figsize=(10.5, 6.5), facecolor=PAPER)
    _style_axis(axis)
    bars = axis.bar(labels, values, color=colors, width=0.58)
    axis.bar_label(bars, labels=[f"{value:.3f}" for value in values], padding=8)
    axis.set_ylabel("Police Visibility Reward (PVR)")
    axis.set_title("Visibility Improvement Across Planning Stages", fontweight="bold")
    axis.text(
        1.0,
        values[1] + max(values) * 0.15,
        f"MaxP gain\n+{values[1] - values[0]:.3f}",
        ha="center",
        color=BLUE,
        fontweight="bold",
    )
    axis.text(
        2.0,
        values[2] + max(values) * 0.15,
        f"Grafting gain\n+{values[2] - values[1]:.3f}",
        ha="center",
        color=GREEN,
        fontweight="bold",
    )
    axis.set_ylim(0, max(values) * 1.38 if max(values) else 1)
    figure.tight_layout()
    _save(figure, output_path)


def build_officer_allocation(
    scenario: PlanningScenario,
    minp_result: MinPResult,
    maxp_result: MaxPResult,
    output_path: Path,
) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(13, 6.2), facecolor=PAPER)

    axes[0].pie(
        [minp_result.selected_officer_count, maxp_result.assigned_officer_count],
        labels=["MinP coverage", "MaxP visibility"],
        autopct="%1.0f%%",
        startangle=90,
        colors=[RED, BLUE],
        wedgeprops={"width": 0.42, "edgecolor": PAPER},
        textprops={"color": INK},
    )
    axes[0].text(
        0,
        0,
        f"{len(scenario.officers)}\nOFFICERS",
        ha="center",
        va="center",
        color=INK,
        fontweight="bold",
        fontsize=16,
    )
    axes[0].set_title("Officer Responsibility", fontweight="bold")

    shifts = list(range(scenario.shifts_per_day))
    counts = [maxp_result.shift_allocation.get(shift, 0) for shift in shifts]
    bars = axes[1].bar(
        [f"Shift {shift}" for shift in shifts],
        counts,
        color=[GOLD, BLUE, GREEN][: len(shifts)],
        width=0.6,
    )
    _style_axis(axes[1])
    axes[1].bar_label(bars, padding=5)
    axes[1].set_ylabel("MaxP officers")
    axes[1].set_title("MaxP Shift Allocation", fontweight="bold")
    axes[1].set_ylim(0, max(counts, default=0) + 2)

    figure.suptitle("Officer Allocation", fontsize=21, color=INK, fontweight="bold")
    figure.tight_layout(rect=(0, 0, 1, 0.93))
    _save(figure, output_path)


def build_incident_coverage_summary(
    scenario: PlanningScenario,
    minp_result: MinPResult,
    output_path: Path,
) -> None:
    covered = len(minp_result.coverage)
    uncovered = len(minp_result.uncovered_request_ids)
    travel_counts = Counter(record.travel_periods for record in minp_result.coverage)
    travel_values = sorted(travel_counts)

    figure, axes = plt.subplots(1, 2, figsize=(13, 6.2), facecolor=PAPER)
    axes[0].pie(
        [covered, uncovered] if uncovered else [covered],
        labels=["Covered", "Uncovered"] if uncovered else ["Covered"],
        startangle=90,
        colors=[GREEN, RED],
        wedgeprops={"width": 0.42, "edgecolor": PAPER},
        textprops={"color": INK},
    )
    axes[0].text(
        0,
        0,
        f"{covered}/{len(scenario.incidents)}\n"
        f"{covered / len(scenario.incidents):.0%}"
        if scenario.incidents
        else "0/0\n100%",
        ha="center",
        va="center",
        color=INK,
        fontweight="bold",
        fontsize=20,
    )
    axes[0].set_title("Incident Coverage", fontweight="bold")

    bars = axes[1].bar(
        [str(value) for value in travel_values],
        [travel_counts[value] for value in travel_values],
        color=[GREEN, BLUE, GOLD, RED][: len(travel_values)],
        width=0.62,
    )
    _style_axis(axes[1])
    axes[1].bar_label(bars, padding=5)
    axes[1].set_xlabel("Travel periods from patrol cell to incident")
    axes[1].set_ylabel("Covered incidents")
    axes[1].set_title("Coverage Response Distance", fontweight="bold")
    axes[1].set_ylim(0, max(travel_counts.values(), default=0) + 3)

    figure.suptitle(
        "Incident Coverage Evaluation",
        fontsize=21,
        color=INK,
        fontweight="bold",
    )
    figure.tight_layout(rect=(0, 0, 1, 0.93))
    _save(figure, output_path)


def build_grafting_summary(
    result: GraftingResult,
    output_path: Path,
) -> None:
    labels = ["Examined windows", "Productive windows", "Added visits"]
    values = [
        result.processed_window_count,
        result.productive_window_count,
        result.added_visit_count,
    ]

    figure, axes = plt.subplots(1, 2, figsize=(13, 6.2), facecolor=PAPER)
    _style_axis(axes[0])
    bars = axes[0].bar(labels, values, color=[MUTED, GOLD, GREEN], width=0.62)
    axes[0].bar_label(bars, padding=5)
    axes[0].tick_params(axis="x", rotation=12)
    axes[0].set_ylabel("Count")
    axes[0].set_title("Grafting Search Activity", fontweight="bold")
    axes[0].set_ylim(0, max(values, default=0) + 4)

    pvr_values = [result.baseline_combined_pvr, result.grafted_combined_pvr]
    pvr_bars = axes[1].bar(
        ["Before grafting", "After grafting"],
        pvr_values,
        color=[BLUE, GREEN],
        width=0.58,
    )
    _style_axis(axes[1])
    axes[1].bar_label(
        pvr_bars,
        labels=[f"{value:.3f}" for value in pvr_values],
        padding=6,
    )
    axes[1].set_ylabel("PVR")
    axes[1].set_title(f"PVR Gain: +{result.grafting_gain:.3f}", fontweight="bold")
    axes[1].set_ylim(0, max(pvr_values) * 1.18 if max(pvr_values) else 1)

    figure.suptitle("Grafting Evaluation", fontsize=21, color=INK, fontweight="bold")
    figure.tight_layout(rect=(0, 0, 1, 0.93))
    _save(figure, output_path)


def build_run_metric_images(
    scenario: PlanningScenario,
    minp_result: MinPResult,
    maxp_result: MaxPResult,
    grafting_result: GraftingResult,
    minp_report: MinPValidationReport,
    grafting_report: GraftingValidationReport,
    stage_seconds: Mapping[str, float],
    output_directory: Path,
) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)
    build_run_summary(
        scenario,
        minp_result,
        maxp_result,
        grafting_result,
        minp_report,
        grafting_report,
        stage_seconds,
        output_directory / "run_summary.png",
    )
    build_pvr_stage_comparison(
        maxp_result,
        grafting_result,
        output_directory / "pvr_stage_comparison.png",
    )
    build_officer_allocation(
        scenario,
        minp_result,
        maxp_result,
        output_directory / "officer_allocation.png",
    )
    build_incident_coverage_summary(
        scenario,
        minp_result,
        output_directory / "incident_coverage_summary.png",
    )
    build_grafting_summary(
        grafting_result,
        output_directory / "grafting_summary.png",
    )
