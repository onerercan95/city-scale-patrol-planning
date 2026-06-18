from __future__ import annotations

from typing import Dict, Iterable, List

import folium

from patrol_planning.domain.models import PlanningScenario


VFOP_COLORS = (
    "#fff7bc",
    "#fee391",
    "#fec44f",
    "#fe9929",
    "#ec7014",
    "#cc4c02",
    "#8c2d04",
)


def aggregate_vfop(
    scenario: PlanningScenario,
    periods: Iterable[int],
) -> Dict[int, float]:
    period_list = list(periods)
    if not period_list:
        raise ValueError("At least one period is required for VFoP aggregation")
    return {
        region.region_id: sum(
            scenario.vfop[(period, region.region_id)] for period in period_list
        )
        / len(period_list)
        for region in scenario.regions
    }


def _normalized(values: Dict[int, float]) -> Dict[int, float]:
    minimum = min(values.values())
    maximum = max(values.values())
    if abs(maximum - minimum) < 1e-12:
        return {region_id: 0.5 for region_id in values}
    return {
        region_id: (value - minimum) / (maximum - minimum)
        for region_id, value in values.items()
    }


def vfop_color(normalized_value: float) -> str:
    index = min(
        int(normalized_value * len(VFOP_COLORS)),
        len(VFOP_COLORS) - 1,
    )
    return VFOP_COLORS[index]


def _add_layer(
    map_view: folium.Map,
    scenario: PlanningScenario,
    name: str,
    periods: List[int],
    show: bool,
) -> None:
    values = aggregate_vfop(scenario, periods)
    scaled = _normalized(values)
    layer = folium.FeatureGroup(name=name, show=show, overlay=True, control=True)
    period_start = min(periods)
    period_end = max(periods)

    for region in scenario.regions:
        value = values[region.region_id]
        normalized_value = scaled[region.region_id]
        folium.Rectangle(
            bounds=[
                [region.min_latitude, region.min_longitude],
                [region.max_latitude, region.max_longitude],
            ],
            color="#5b4636",
            weight=0.8,
            fill=True,
            fill_color=vfop_color(normalized_value),
            fill_opacity=0.18 + 0.52 * normalized_value,
            tooltip=(
                f"Region {region.region_id} | {name} | "
                f"mean VFoP {value:.3f} | relative density "
                f"{normalized_value:.0%} | periods {period_start}-{period_end}"
            ),
        ).add_to(layer)
    layer.add_to(map_view)


def add_vfop_layers(
    map_view: folium.Map,
    scenario: PlanningScenario,
) -> None:
    _add_layer(
        map_view,
        scenario,
        name="VFoP: full-day average",
        periods=list(range(scenario.periods)),
        show=True,
    )
    for shift in range(scenario.shifts_per_day):
        start = shift * scenario.periods_per_shift
        end = start + scenario.periods_per_shift
        _add_layer(
            map_view,
            scenario,
            name=f"VFoP: shift {shift}",
            periods=list(range(start, end)),
            show=False,
        )


def add_vfop_legend(map_view: folium.Map) -> None:
    swatches = "".join(
        f'<span style="display:inline-block;width:24px;height:12px;'
        f'background:{color};"></span>'
        for color in VFOP_COLORS
    )
    legend = f"""
    <div style="
        position: fixed; bottom: 34px; right: 18px; z-index: 9999;
        background: rgba(255,255,255,0.94); border: 1px solid #8c6d4f;
        border-radius: 6px; padding: 10px 12px;
        font: 12px sans-serif; color: #322a24;">
      <strong>Relative VFoP density</strong><br>
      <span style="font-size:11px;">low</span>
      <span style="margin:0 4px;">{swatches}</span>
      <span style="font-size:11px;">high</span><br>
      <span style="font-size:10px;color:#66584c;">
        Use layer control to switch day/shift view
      </span>
    </div>
    """
    map_view.get_root().html.add_child(folium.Element(legend))
