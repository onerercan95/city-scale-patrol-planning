from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/patrol-planning-matplotlib")

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def build_baseline_comparison_charts(
    comparison_csv: Path,
    data_output_directory: Path,
    image_output_directory: Path,
) -> None:
    data_output_directory.mkdir(parents=True, exist_ok=True)
    image_output_directory.mkdir(parents=True, exist_ok=True)
    results = pd.read_csv(comparison_csv)
    summary = (
        results.groupby(["algorithm", "officer_count"], as_index=False)
        .agg(
            incident_count=("incident_count", "mean"),
            coverage_rate=("coverage_rate", "mean"),
            coverage_std=("coverage_rate", "std"),
            pvr=("pvr", "mean"),
            pvr_std=("pvr", "std"),
            runtime_seconds=("runtime_seconds", "mean"),
            runtime_std=("runtime_seconds", "std"),
            complete_coverage_rate=("complete_coverage", "mean"),
            valid_rate=("valid", "mean"),
        )
        .sort_values(["officer_count", "algorithm"])
    )
    summary.to_csv(
        data_output_directory / "baseline_comparison_summary.csv",
        index=False,
    )

    sns.set_theme(style="whitegrid", context="talk")
    palette = {
        "MinP-MaxP-Grafting": "#ba3b2f",
        "Greedy Visibility": "#287271",
        "Static Checkpoints": "#d99b2b",
    }
    figure, axes = plt.subplots(1, 3, figsize=(20, 6.5))

    sns.lineplot(
        data=results,
        x="officer_count",
        y="coverage_rate",
        hue="algorithm",
        style="algorithm",
        markers=True,
        dashes=False,
        errorbar="sd",
        palette=palette,
        ax=axes[0],
    )
    axes[0].set_title("Incident Coverage")
    axes[0].set_ylabel("Coverage rate")
    axes[0].set_ylim(0, 1.05)

    sns.lineplot(
        data=results,
        x="officer_count",
        y="pvr",
        hue="algorithm",
        style="algorithm",
        markers=True,
        dashes=False,
        errorbar="sd",
        palette=palette,
        legend=False,
        ax=axes[1],
    )
    axes[1].set_title("Police Visibility Reward")
    axes[1].set_ylabel("PVR")

    sns.lineplot(
        data=results,
        x="officer_count",
        y="runtime_seconds",
        hue="algorithm",
        style="algorithm",
        markers=True,
        dashes=False,
        errorbar="sd",
        palette=palette,
        legend=False,
        ax=axes[2],
    )
    axes[2].set_title("Planning Runtime")
    axes[2].set_ylabel("Seconds")
    axes[2].set_yscale("log")

    for axis in axes:
        axis.set_xlabel("Available officers")
        axis.set_xticks(sorted(results["officer_count"].unique()))

    figure.suptitle(
        "Patrol Planning Baselines on Seeded Poisson Scenarios",
        fontsize=22,
        fontweight="bold",
    )
    figure.tight_layout(rect=(0, 0, 1, 0.92))
    figure.savefig(
        image_output_directory / "baseline_comparison_dashboard.png",
        dpi=180,
    )
    plt.close(figure)
