from __future__ import annotations

from itertools import cycle
from pathlib import Path

import folium

from patrol_planning.domain.models import PlanningScenario
from patrol_planning.domain.routes import GraftingResult, MaxPResult, MinPResult
from patrol_planning.time.periods import period_label
from patrol_planning.visualization.combined_map import _draw_routes
from patrol_planning.visualization.minp_map import ROUTE_COLORS
from patrol_planning.visualization.vfop_layers import (
    add_vfop_layers,
    add_vfop_legend,
)


def build_final_map(
    scenario: PlanningScenario,
    minp_result: MinPResult,
    maxp_result: MaxPResult,
    grafting_result: GraftingResult,
    output_path: Path,
) -> None:
    regions = {region.region_id: region for region in scenario.regions}
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

    _draw_routes(
        map_view,
        scenario,
        grafting_result.grafted_minp_routes,
        "Grafted MinP",
        dashed=False,
    )
    _draw_routes(map_view, scenario, maxp_result.routes, "MaxP", dashed=True)

    for (officer_id, visits), color in zip(
        sorted(grafting_result.added_visits.items()),
        cycle(ROUTE_COLORS),
    ):
        for visit in visits:
            region = regions[visit.region_id]
            folium.CircleMarker(
                location=[region.center_latitude, region.center_longitude],
                radius=5,
                color="#111827",
                weight=2,
                fill=True,
                fill_color=color,
                fill_opacity=1,
                tooltip=(
                    f"Graft officer {officer_id} | "
                    f"{period_label(visit.period, period_minutes)} | "
                    f"region {visit.region_id}"
                ),
            ).add_to(map_view)

    legend = """
    <div style="
        position: fixed; bottom: 28px; left: 28px; z-index: 9999;
        background: white; border: 1px solid #66788a; border-radius: 6px;
        padding: 10px 14px; font: 13px sans-serif; color: #1f2933;">
      <strong>Final patrol plan</strong><br>
      <span style="display:inline-block;width:28px;border-top:4px solid #30638e;
                   margin-right:7px;vertical-align:middle;"></span>Grafted MinP route<br>
      <span style="display:inline-block;width:28px;border-top:3px dashed #d1495b;
                   margin-right:7px;vertical-align:middle;"></span>MaxP route<br>
      <span style="font-size:18px;color:#111827;">●</span> Added graft visit<br>
      <span style="color:#20a47e;">●</span> Covered incident
    </div>
    """
    map_view.get_root().html.add_child(folium.Element(legend))
    add_vfop_legend(map_view)
    folium.LayerControl(collapsed=False).add_to(map_view)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    map_view.save(str(output_path))
