from pathlib import Path

import folium

from patrol_planning.domain.models import PlanningScenario
from patrol_planning.domain.routes import MaxPResult
from patrol_planning.visualization.combined_map import _draw_routes
from patrol_planning.visualization.vfop_layers import (
    add_vfop_layers,
    add_vfop_legend,
)


def build_maxp_map(
    scenario: PlanningScenario,
    result: MaxPResult,
    output_path: Path,
) -> None:
    """Build a map containing only MaxP visibility routes."""
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
    _draw_routes(map_view, scenario, result.routes, "MaxP", dashed=True)

    legend = """
    <div style="
        position: fixed; bottom: 28px; left: 28px; z-index: 9999;
        background: white; border: 1px solid #66788a; border-radius: 6px;
        padding: 10px 14px; font: 13px sans-serif; color: #1f2933;">
      <strong>MaxP visibility routes</strong><br>
      <span style="display:inline-block;width:28px;border-top:3px dashed #d1495b;
                   margin-right:7px;vertical-align:middle;"></span>
      Remaining-officer patrol route<br>
      <span style="font-size:11px;color:#52606d;">
        Routes maximize VFoP after MinP coverage.
      </span>
    </div>
    """
    map_view.get_root().html.add_child(folium.Element(legend))
    add_vfop_legend(map_view)
    folium.LayerControl(collapsed=False).add_to(map_view)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    map_view.save(str(output_path))
