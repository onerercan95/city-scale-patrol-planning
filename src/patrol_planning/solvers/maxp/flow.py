from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from ortools.graph.python import min_cost_flow

from patrol_planning.domain.models import PlanningScenario
from patrol_planning.domain.routes import PatrolVisit


@dataclass(frozen=True)
class FixedShiftSolution:
    shift: int
    officer_count: int
    routes: Tuple[Tuple[PatrolVisit, ...], ...]
    pvr: float


def solve_fixed_shift(
    scenario: PlanningScenario,
    shift: int,
    officer_count: int,
    cost_scale: int,
) -> FixedShiftSolution:
    if officer_count == 0:
        return FixedShiftSolution(shift, 0, (), 0.0)
    if not 0 <= shift < scenario.shifts_per_day:
        raise ValueError(f"Invalid shift: {shift}")
    if officer_count > len(scenario.regions):
        raise ValueError("Officer count exceeds available start-region capacity")

    shift_start = shift * scenario.periods_per_shift
    shift_end = shift_start + scenario.periods_per_shift
    source = 0
    sink = 1
    next_node = 2
    in_node: Dict[Tuple[int, int], int] = {}
    out_node: Dict[Tuple[int, int], int] = {}
    visit_for_in: Dict[int, PatrolVisit] = {}

    for period in range(shift_start, shift_end):
        for region in scenario.regions:
            in_node[(period, region.region_id)] = next_node
            visit_for_in[next_node] = PatrolVisit(period, region.region_id)
            next_node += 1
            out_node[(period, region.region_id)] = next_node
            next_node += 1

    flow = min_cost_flow.SimpleMinCostFlow()
    source_arc_by_in: Dict[int, int] = {}
    transition_arc_to_in: Dict[int, int] = {}

    for key, node_in in in_node.items():
        period, region_id = key
        source_arc_by_in[node_in] = flow.add_arc_with_capacity_and_unit_cost(
            source,
            node_in,
            1,
            0,
        )
        reward_cost = -round(scenario.vfop[(period, region_id)] * cost_scale)
        flow.add_arc_with_capacity_and_unit_cost(
            node_in,
            out_node[key],
            1,
            reward_cost,
        )
        flow.add_arc_with_capacity_and_unit_cost(
            out_node[key],
            sink,
            1,
            0,
        )

    for period in range(shift_start, shift_end):
        for source_region in scenario.regions:
            node_out = out_node[(period, source_region.region_id)]
            for target_region in scenario.regions:
                travel = scenario.travel_periods[
                    (source_region.region_id, target_region.region_id)
                ]
                arrival = period + travel + 1
                if arrival >= shift_end:
                    continue
                target_in = in_node[(arrival, target_region.region_id)]
                arc = flow.add_arc_with_capacity_and_unit_cost(
                    node_out,
                    target_in,
                    1,
                    0,
                )
                transition_arc_to_in[arc] = target_in

    flow.set_node_supply(source, officer_count)
    flow.set_node_supply(sink, -officer_count)
    status = flow.solve()
    if status != flow.OPTIMAL:
        raise RuntimeError(f"MaxP min-cost flow failed with status {status}")

    starts = [
        node_in
        for node_in, arc in source_arc_by_in.items()
        if flow.flow(arc) == 1
    ]
    next_in_by_out = {
        flow.tail(arc): target_in
        for arc, target_in in transition_arc_to_in.items()
        if flow.flow(arc) == 1
    }
    routes: List[Tuple[PatrolVisit, ...]] = []
    for start in sorted(
        starts,
        key=lambda node: (
            visit_for_in[node].period,
            visit_for_in[node].region_id,
        ),
    ):
        route: List[PatrolVisit] = []
        current_in = start
        while True:
            visit = visit_for_in[current_in]
            route.append(visit)
            current_out = out_node[(visit.period, visit.region_id)]
            next_in = next_in_by_out.get(current_out)
            if next_in is None:
                break
            current_in = next_in
        routes.append(tuple(route))

    pvr = round(
        sum(
            scenario.vfop[(visit.period, visit.region_id)]
            for route in routes
            for visit in route
        ),
        6,
    )
    return FixedShiftSolution(
        shift=shift,
        officer_count=officer_count,
        routes=tuple(routes),
        pvr=pvr,
    )
