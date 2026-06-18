from __future__ import annotations

from itertools import cycle
from pathlib import Path

import folium

from patrol_planning.domain.models import PlanningScenario
from patrol_planning.domain.routes import MinPResult
from patrol_planning.time.periods import period_label
from patrol_planning.visualization.vfop_layers import (
    add_vfop_layers,
    add_vfop_legend,
)


ROUTE_COLORS = (
    "#d1495b",
    "#00798c",
    "#edae49",
    "#30638e",
    "#5f4b8b",
    "#2a9d8f",
    "#e76f51",
    "#6a994e",
    "#bc6c25",
    "#8338ec",
)


def build_minp_map(
    scenario: PlanningScenario,
    result: MinPResult,
    output_path: Path,
) -> None:
    regions_by_id = {region.region_id: region for region in scenario.regions}
    center_latitude = sum(region.center_latitude for region in scenario.regions) / len(
        scenario.regions
    )
    center_longitude = sum(region.center_longitude for region in scenario.regions) / len(
        scenario.regions
    )
    map_view = folium.Map(
        location=[center_latitude, center_longitude],
        zoom_start=13,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    add_vfop_layers(map_view, scenario)

    covered = {coverage.request_id for coverage in result.coverage}
    period_minutes = 1440 // scenario.periods
    for incident in scenario.incidents:
        is_covered = incident.request_id in covered
        folium.CircleMarker(
            location=[incident.latitude, incident.longitude],
            radius=4,
            color="#147d64" if is_covered else "#b42318",
            fill=True,
            fill_color="#20a47e" if is_covered else "#e5484d",
            fill_opacity=0.9,
            tooltip=(
                f"{incident.request_id} | {incident.category} | "
                f"{period_label(incident.period, period_minutes)} | "
                f"{'covered' if is_covered else 'uncovered'}"
            ),
        ).add_to(map_view)

    for route, color in zip(result.routes, cycle(ROUTE_COLORS)):
        points = [
            [
                regions_by_id[visit.region_id].center_latitude,
                regions_by_id[visit.region_id].center_longitude,
            ]
            for visit in route.visits
        ]
        if len(points) > 1:
            folium.PolyLine(
                points,
                color=color,
                weight=4,
                opacity=0.85,
                tooltip=f"Officer {route.officer_id} | shift {route.shift}",
            ).add_to(map_view)
        for visit, point in zip(route.visits, points):
            folium.CircleMarker(
                location=point,
                radius=3,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=1,
                tooltip=(
                    f"Officer {route.officer_id} | shift {route.shift} | "
                    f"{period_label(visit.period, period_minutes)} | "
                    f"region {visit.region_id}"
                ),
            ).add_to(map_view)

    add_vfop_legend(map_view)
    folium.LayerControl(collapsed=False).add_to(map_view)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    map_view.save(str(output_path))
