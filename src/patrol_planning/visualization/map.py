from __future__ import annotations

from pathlib import Path

import folium

from patrol_planning.domain.models import PlanningScenario
from patrol_planning.time.periods import period_label
from patrol_planning.visualization.vfop_layers import (
    add_vfop_layers,
    add_vfop_legend,
)


def build_scenario_map(
    scenario: PlanningScenario,
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

    for incident in scenario.incidents:
        folium.CircleMarker(
            location=[incident.latitude, incident.longitude],
            radius=4,
            color="#b51f1f",
            fill=True,
            fill_color="#f04444",
            fill_opacity=0.85,
            tooltip=(
                f"{incident.request_id} | {incident.category} | "
                f"{period_label(incident.period, 1440 // scenario.periods)} | "
                f"region {incident.region_id}"
            ),
        ).add_to(map_view)

    add_vfop_legend(map_view)
    folium.LayerControl(collapsed=False).add_to(map_view)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    map_view.save(str(output_path))
