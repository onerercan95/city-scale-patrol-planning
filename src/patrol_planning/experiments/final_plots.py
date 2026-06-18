from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/patrol-planning-matplotlib")

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def _with_grid_label(results: pd.DataFrame) -> pd.DataFrame:
    labeled = results.copy()
    labeled["grid"] = (
        labeled["grid_rows"].astype(str)
        + "x"
        + labeled["grid_columns"].astype(str)
    )
    return labeled


def build_final_evaluation_charts(
    evaluation_csv: Path,
    data_output_directory: Path,
    image_output_directory: Path,
) -> None:
    data_output_directory.mkdir(parents=True, exist_ok=True)
    image_output_directory.mkdir(parents=True, exist_ok=True)
    results = _with_grid_label(pd.read_csv(evaluation_csv))
    feasible = results[results["feasible"]]

    by_count = (
        results.groupby(["grid", "officer_count"], as_index=False)
        .agg(
            scenario_count=("seed", "count"),
            incident_count=("incident_count", "mean"),
            feasibility_rate=("feasible", "mean"),
            coverage_rate=("coverage_rate", "mean"),
            minp_required=("minp_required", "mean"),
            grafted_pvr=("grafted_pvr", "mean"),
            grafting_gain=("grafting_gain", "mean"),
            total_solver_seconds=("total_solver_seconds", "mean"),
            valid_rate=("valid", "mean"),
            truncation_rate=("minp_search_truncated", "mean"),
        )
        .sort_values(["grid", "officer_count"])
    )
    by_count.to_csv(
        data_output_directory / "final_evaluation_summary.csv",
        index=False,
    )

    thresholds = (
        results[
            [
                "grid",
                "seed",
                "incident_count",
                "minp_required",
                "minp_search_truncated",
            ]
        ]
        .drop_duplicates()
        .sort_values(["grid", "seed"])
    )
    thresholds.to_csv(
        data_output_directory / "feasibility_thresholds.csv",
        index=False,
    )

    sns.set_theme(style="whitegrid", context="talk")
    palette = {"10x10": "#287271", "12x12": "#c44536", "15x15": "#d99b2b"}
    figure, axes = plt.subplots(2, 2, figsize=(17, 12))

    sns.lineplot(
        data=results,
        x="officer_count",
        y="feasible",
        hue="grid",
        marker="o",
        errorbar=None,
        palette=palette,
        ax=axes[0, 0],
    )
    axes[0, 0].set_title("Feasibility Boundary")
    axes[0, 0].set_ylabel("Feasible-scenario rate")
    axes[0, 0].set_ylim(-0.03, 1.03)

    sns.boxplot(
        data=thresholds,
        x="grid",
        y="minp_required",
        hue="grid",
        palette=palette,
        legend=False,
        ax=axes[0, 1],
    )
    sns.stripplot(
        data=thresholds,
        x="grid",
        y="minp_required",
        color="#282828",
        size=6,
        jitter=0.14,
        ax=axes[0, 1],
    )
    axes[0, 1].set_title("Minimum Officers Required")
    axes[0, 1].set_ylabel("MinP officers")

    sns.lineplot(
        data=feasible,
        x="officer_count",
        y="grafted_pvr",
        hue="grid",
        marker="o",
        errorbar="sd",
        palette=palette,
        legend=False,
        ax=axes[1, 0],
    )
    axes[1, 0].set_title("Final Visibility Reward")
    axes[1, 0].set_ylabel("PVR after grafting")

    sns.lineplot(
        data=feasible,
        x="officer_count",
        y="total_solver_seconds",
        hue="grid",
        marker="o",
        errorbar="sd",
        palette=palette,
        legend=False,
        ax=axes[1, 1],
    )
    axes[1, 1].set_title("Solver Runtime")
    axes[1, 1].set_ylabel("Seconds")

    officer_ticks = sorted(results["officer_count"].unique())
    for axis in (axes[0, 0], axes[1, 0], axes[1, 1]):
        axis.set_xlabel("Available officers")
        axis.set_xticks(officer_ticks)
        axis.tick_params(axis="x", rotation=35)
    axes[0, 1].set_xlabel("Grid resolution")

    figure.suptitle(
        "Final Evaluation: Demand Seeds, Feasibility, and Grid Resolution",
        fontsize=22,
        fontweight="bold",
    )
    figure.tight_layout(rect=(0, 0, 1, 0.95))
    figure.savefig(
        image_output_directory / "final_evaluation_dashboard.png",
        dpi=180,
    )
    plt.close(figure)

    pivot = thresholds.pivot(index="seed", columns="grid", values="minp_required")
    figure, axis = plt.subplots(figsize=(10, 7))
    sns.heatmap(
        pivot,
        annot=True,
        fmt=".0f",
        cmap="YlOrRd",
        cbar_kws={"label": "Minimum officers"},
        ax=axis,
    )
    axis.set_title("Coverage Feasibility Threshold by Seed")
    axis.set_xlabel("Grid resolution")
    axis.set_ylabel("Poisson seed")
    figure.tight_layout()
    figure.savefig(
        image_output_directory / "feasibility_threshold_heatmap.png",
        dpi=180,
    )
    plt.close(figure)
