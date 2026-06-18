from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from patrol_planning.output.layout import data_directory


_COVERAGE_COLORS = {
    0: "#16a34a",
    1: "#2563eb",
    2: "#f97316",
}


def build_coverage_explanation_plot(
    artifact_directory: Path,
    output_path: Path,
    *,
    title: str | None = None,
    show_reading_tip: bool = True,
) -> None:
    """Create a static visual explaining route movement vs incident coverage."""
    artifact_directory = Path(artifact_directory)
    data_path = data_directory(artifact_directory)
    regions = pd.read_csv(data_path / "regions.csv")
    incidents = pd.read_csv(data_path / "planning_incidents.csv")
    coverage = pd.read_csv(data_path / "minp_coverage.csv")
    routes = pd.read_csv(data_path / "minp_routes.csv")

    regions_by_id = regions.set_index("region_id")
    incidents_by_id = incidents.set_index("request_id")

    fig, ax = plt.subplots(figsize=(14, 9), dpi=160)

    for _, region in regions.iterrows():
        ax.add_patch(
            plt.Rectangle(
                (region.min_longitude, region.min_latitude),
                region.max_longitude - region.min_longitude,
                region.max_latitude - region.min_latitude,
                fill=False,
                edgecolor="#cbd5e1",
                linewidth=0.45,
                zorder=1,
            )
        )

    # Route movement lines are deliberately muted: they are travel feasibility,
    # not the proof that a specific incident is covered.
    for _, route in routes.groupby("officer_id"):
        route = route.sort_values("period")
        points = [
            (
                regions_by_id.loc[int(row.region_id)].center_longitude,
                regions_by_id.loc[int(row.region_id)].center_latitude,
            )
            for row in route.itertuples()
        ]
        if len(points) > 1:
            xs, ys = zip(*points)
            ax.plot(
                xs,
                ys,
                color="#64748b",
                linewidth=1.4,
                alpha=0.32,
                zorder=2,
            )

    # Dashed links are the important part: each link connects an incident to the
    # patrol region that independently validates its coverage.
    for row in coverage.itertuples():
        incident = incidents_by_id.loc[row.request_id]
        officer_region = regions_by_id.loc[int(row.officer_region_id)]
        color = _COVERAGE_COLORS.get(int(row.travel_periods), "#7c3aed")
        x1 = officer_region.center_longitude
        y1 = officer_region.center_latitude
        x2 = incident.longitude
        y2 = incident.latitude
        if int(row.travel_periods) == 0:
            ax.scatter(
                [x2],
                [y2],
                s=155,
                facecolors="none",
                edgecolors=color,
                linewidths=2.1,
                zorder=5,
            )
        else:
            ax.plot(
                [x1, x2],
                [y1, y2],
                color=color,
                linewidth=1.9,
                linestyle=(0, (4, 4)),
                alpha=0.9,
                zorder=4,
            )

    ax.scatter(
        incidents["longitude"],
        incidents["latitude"],
        s=42,
        c="#111827",
        edgecolors="white",
        linewidths=0.55,
        label="incident request",
        zorder=6,
    )

    route_visit_regions = routes["region_id"].drop_duplicates()
    route_visit_points = regions_by_id.loc[route_visit_regions]
    ax.scatter(
        route_visit_points["center_longitude"],
        route_visit_points["center_latitude"],
        s=32,
        c="#64748b",
        marker="s",
        alpha=0.75,
        label="MinP patrol visit cell",
        zorder=3,
    )

    violations = coverage[coverage.travel_periods > coverage.response_limit_periods]
    title_suffix = (
        "0 coverage violations"
        if violations.empty
        else f"{len(violations)} coverage violations"
    )
    if title is None:
        title = (
            "Incident Coverage vs Route Movement\n"
            f"Dashed links show which patrol cell covers each incident ({title_suffix})"
        )
    ax.set_title(title, fontsize=18, fontweight="bold", pad=14)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(alpha=0.16)

    legend_items = [
        Line2D([0], [0], color="#64748b", lw=2, alpha=0.45, label="route movement between patrol visits"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#111827", markeredgecolor="white", markersize=8, label="incident request"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor="#64748b", markersize=7, label="patrol visit cell"),
        Patch(facecolor="none", edgecolor=_COVERAGE_COLORS[0], linewidth=2, label="coverage travel 0 periods"),
        Line2D([0], [0], color=_COVERAGE_COLORS[1], lw=2, linestyle=(0, (4, 4)), label="coverage travel 1 period"),
        Line2D([0], [0], color=_COVERAGE_COLORS[2], lw=2, linestyle=(0, (4, 4)), label="coverage travel 2 periods"),
    ]
    ax.legend(
        handles=legend_items,
        loc="upper right",
        frameon=True,
        framealpha=0.96,
        fontsize=10,
    )

    if show_reading_tip:
        ax.text(
            0.01,
            0.01,
            "Reading tip: a long solid route segment is only movement between visits. "
            "Incident coverage is proven by the dashed link and its travel/limit value.",
            transform=ax.transAxes,
            fontsize=10.5,
            color="#334155",
            bbox={
                "boxstyle": "round,pad=0.45",
                "facecolor": "#f8fafc",
                "edgecolor": "#cbd5e1",
                "alpha": 0.96,
            },
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)
