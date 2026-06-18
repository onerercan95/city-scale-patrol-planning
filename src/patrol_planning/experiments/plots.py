from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/patrol-planning-matplotlib")

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def _aggregate(results: pd.DataFrame) -> pd.DataFrame:
    numeric_columns = [
        "coverage_rate",
        "minp_officers",
        "maxp_officers",
        "combined_pvr",
        "grafted_pvr",
        "grafting_gain",
        "grafting_gain_percent",
        "total_seconds",
    ]
    summary = (
        results.groupby("officer_count", as_index=False)[numeric_columns]
        .mean()
        .sort_values("officer_count")
    )
    feasibility = (
        results.groupby("officer_count", as_index=False)["feasible"]
        .mean()
        .rename(columns={"feasible": "feasibility_rate"})
    )
    return summary.merge(feasibility, on="officer_count")


def build_experiment_charts(
    experiments_csv: Path,
    data_output_directory: Path,
    image_output_directory: Path,
) -> None:
    data_output_directory.mkdir(parents=True, exist_ok=True)
    image_output_directory.mkdir(parents=True, exist_ok=True)
    results = pd.read_csv(experiments_csv)
    summary = _aggregate(results)
    summary.to_csv(data_output_directory / "experiment_summary.csv", index=False)

    sns.set_theme(style="whitegrid", context="talk")
    palette = {
        "combined": "#366e8d",
        "grafted": "#d9772a",
        "coverage": "#27896d",
        "runtime": "#934f7c",
    }
    figure, axes = plt.subplots(2, 2, figsize=(16, 11))

    feasible = results[results["feasible"]]
    sns.lineplot(
        data=feasible,
        x="officer_count",
        y="combined_pvr",
        marker="o",
        errorbar="sd",
        color=palette["combined"],
        label="MinP + MaxP",
        ax=axes[0, 0],
    )
    sns.lineplot(
        data=feasible,
        x="officer_count",
        y="grafted_pvr",
        marker="s",
        errorbar="sd",
        color=palette["grafted"],
        label="After grafting",
        ax=axes[0, 0],
    )
    axes[0, 0].set_title("Visibility Reward vs Officer Count")
    axes[0, 0].set_ylabel("PVR")

    sns.lineplot(
        data=results,
        x="officer_count",
        y="coverage_rate",
        marker="o",
        errorbar="sd",
        color=palette["coverage"],
        ax=axes[0, 1],
    )
    axes[0, 1].set_title("Incident Coverage")
    axes[0, 1].set_ylabel("Coverage rate")
    axes[0, 1].set_ylim(0, 1.05)

    sns.lineplot(
        data=feasible,
        x="officer_count",
        y="grafting_gain_percent",
        marker="o",
        errorbar="sd",
        color=palette["grafted"],
        ax=axes[1, 0],
    )
    axes[1, 0].set_title("Relative Grafting Improvement")
    axes[1, 0].set_ylabel("PVR gain (%)")

    sns.lineplot(
        data=results,
        x="officer_count",
        y="total_seconds",
        marker="o",
        errorbar="sd",
        color=palette["runtime"],
        ax=axes[1, 1],
    )
    axes[1, 1].set_title("End-to-End Runtime")
    axes[1, 1].set_ylabel("Seconds")

    for axis in axes.flat:
        axis.set_xlabel("Available officers")
        axis.set_xticks(sorted(results["officer_count"].unique()))

    figure.suptitle(
        "Central LA Patrol Planning: Five January 2023 Replay Days",
        fontsize=22,
        fontweight="bold",
    )
    figure.tight_layout(rect=(0, 0, 1, 0.96))
    figure.savefig(image_output_directory / "experiment_dashboard.png", dpi=180)
    plt.close(figure)

    allocation = (
        feasible.groupby("officer_count", as_index=False)[
            ["minp_officers", "maxp_officers"]
        ]
        .mean()
        .set_index("officer_count")
    )
    axis = allocation.plot(
        kind="bar",
        stacked=True,
        color=["#b14d4d", "#366e8d"],
        figsize=(11, 7),
    )
    axis.set_title("Average Officer Allocation")
    axis.set_xlabel("Available officers")
    axis.set_ylabel("Officers")
    axis.legend(["MinP incident coverage", "MaxP visibility"])
    axis.figure.tight_layout()
    axis.figure.savefig(image_output_directory / "officer_allocation.png", dpi=180)
    plt.close(axis.figure)

    pivot = results.pivot(
        index="replay_date",
        columns="officer_count",
        values="coverage_rate",
    )
    figure, axis = plt.subplots(figsize=(11, 6))
    sns.heatmap(
        pivot,
        annot=True,
        fmt=".2f",
        cmap="YlGn",
        vmin=0,
        vmax=1,
        cbar_kws={"label": "Coverage rate"},
        ax=axis,
    )
    axis.set_title("Coverage Feasibility by Replay Day")
    axis.set_xlabel("Available officers")
    axis.set_ylabel("Replay date")
    figure.tight_layout()
    figure.savefig(image_output_directory / "coverage_heatmap.png", dpi=180)
    plt.close(figure)
