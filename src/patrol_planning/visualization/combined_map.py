from __future__ import annotations

from itertools import cycle
from pathlib import Path

import folium

from patrol_planning.domain.models import PlanningScenario
from patrol_planning.domain.routes import MaxPResult, MinPResult, OfficerRoute
from patrol_planning.time.periods import period_label
from patrol_planning.visualization.minp_map import ROUTE_COLORS
from patrol_planning.visualization.vfop_layers import (
    add_vfop_layers,
    add_vfop_legend,
)


def _draw_routes(
    map_view: folium.Map,
    scenario: PlanningScenario,
    routes: list[OfficerRoute],
    prefix: str,
    dashed: bool,
) -> None:
    regions = {region.region_id: region for region in scenario.regions}
    period_minutes = 1440 // scenario.periods
    for route, color in zip(routes, cycle(ROUTE_COLORS)):
        points = [
            [
                regions[visit.region_id].center_latitude,
                regions[visit.region_id].center_longitude,
            ]
            for visit in route.visits
        ]
        if len(points) > 1:
            folium.PolyLine(
                points,
                color=color,
                weight=4 if not dashed else 3,
                opacity=0.8,
                dash_array="8 6" if dashed else None,
                tooltip=f"{prefix} officer {route.officer_id} | shift {route.shift}",
            ).add_to(map_view)
        for visit, point in zip(route.visits, points):
            folium.CircleMarker(
                location=point,
                radius=3 if not dashed else 2,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.9,
                tooltip=(
                    f"{prefix} officer {route.officer_id} | "
                    f"{period_label(visit.period, period_minutes)} | "
                    f"region {visit.region_id}"
                ),
            ).add_to(map_view)


def build_combined_map(
    scenario: PlanningScenario,
    minp_result: MinPResult,
    maxp_result: MaxPResult,
    output_path: Path,
) -> None:
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

    covered = {coverage.request_id for coverage in minp_result.coverage}
    period_minutes = 1440 // scenario.periods
    for incident in scenario.incidents:
        folium.CircleMarker(
            location=[incident.latitude, incident.longitude],
            radius=4,
            color="#147d64" if incident.request_id in covered else "#b42318",
            fill=True,
            fill_color="#20a47e" if incident.request_id in covered else "#e5484d",
            fill_opacity=0.9,
            tooltip=(
                f"{incident.request_id} | {incident.category} | "
                f"{period_label(incident.period, period_minutes)}"
            ),
        ).add_to(map_view)

    _draw_routes(map_view, scenario, minp_result.routes, "MinP", dashed=False)
    _draw_routes(map_view, scenario, maxp_result.routes, "MaxP", dashed=True)
    legend = """
    <div style="
        position: fixed; bottom: 28px; left: 28px; z-index: 9999;
        background: white; border: 1px solid #66788a; border-radius: 6px;
        padding: 10px 14px; font: 13px sans-serif; color: #1f2933;">
      <strong>Patrol routes</strong><br>
      <span style="display:inline-block;width:28px;border-top:4px solid #30638e;
                   margin-right:7px;vertical-align:middle;"></span>MinP coverage<br>
      <span style="display:inline-block;width:28px;border-top:3px dashed #d1495b;
                   margin-right:7px;vertical-align:middle;"></span>MaxP visibility<br>
      <span style="color:#20a47e;">●</span> Covered incident
    </div>
    """
    map_view.get_root().html.add_child(folium.Element(legend))
    add_vfop_legend(map_view)
    folium.LayerControl(collapsed=False).add_to(map_view)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    map_view.save(str(output_path))
