from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from patrol_planning.config.models import AppConfig
from patrol_planning.demand.classification import classify_incident
from patrol_planning.demand.poisson import (
    PoissonRate,
    learn_poisson_rates,
    sample_poisson_incidents,
)
from patrol_planning.demand.vfop import estimate_vfop
from patrol_planning.domain.models import (
    HistoricalIncident,
    PlanningIncident,
    PlanningScenario,
)
from patrol_planning.geography.grid import Grid, build_grid
from patrol_planning.time.periods import period_for_datetime
from patrol_planning.travel.grid import build_grid_travel_matrix


@dataclass
class ScenarioBuildResult:
    scenario: PlanningScenario
    grid: Grid
    historical_incidents: List[HistoricalIncident]
    poisson_rates: List[PoissonRate] = field(default_factory=list)


def _build_common_inputs(
    config: AppConfig,
    historical_incidents: List[HistoricalIncident],
) -> Tuple[
    Grid,
    Dict[Tuple[int, int], float],
    Dict[Tuple[int, int], int],
]:
    if not historical_incidents:
        raise ValueError("The configured historical slice contains no valid incidents")

    grid = build_grid(
        historical_incidents,
        rows=config.grid.rows,
        columns=config.grid.columns,
    )
    vfop = estimate_vfop(
        historical_incidents,
        grid,
        periods=config.time.periods_per_day,
        period_minutes=config.time.period_minutes,
        baseline=config.vfop.baseline,
    )
    travel_periods = build_grid_travel_matrix(
        grid.regions,
        config.travel.periods_per_grid_step,
    )
    return grid, vfop, travel_periods


def _build_scenario(
    config: AppConfig,
    historical_incidents: List[HistoricalIncident],
    grid: Grid,
    planning_incidents: List[PlanningIncident],
    vfop: Dict[Tuple[int, int], float],
    travel_periods: Dict[Tuple[int, int], int],
    metadata: Dict[str, object],
    poisson_rates: Optional[List[PoissonRate]] = None,
) -> ScenarioBuildResult:
    scenario = PlanningScenario(
        name=config.run_name,
        periods=config.time.periods_per_day,
        shifts_per_day=config.time.shifts_per_day,
        periods_per_shift=config.time.periods_per_shift,
        officers=list(range(1, config.scenario.officers + 1)),
        regions=grid.regions,
        incidents=planning_incidents,
        vfop=vfop,
        travel_periods=travel_periods,
        metadata={
            "source": "LA Crime Data 2020-2024",
            "area_name": config.data.area_name,
            "history_start": config.data.history_start.isoformat(),
            "history_end": config.data.history_end.isoformat(),
            "scenario_mode": config.scenario.mode,
            "period_minutes": config.time.period_minutes,
            "grid_rows": config.grid.rows,
            "grid_columns": config.grid.columns,
            "vfop_method": "normalized historical incident density",
            "travel_method": "Manhattan grid distance",
            **metadata,
        },
    )
    return ScenarioBuildResult(
        scenario=scenario,
        grid=grid,
        historical_incidents=historical_incidents,
        poisson_rates=poisson_rates or [],
    )


def build_replay_scenario(
    config: AppConfig,
    historical_incidents: List[HistoricalIncident],
) -> ScenarioBuildResult:
    grid, vfop, travel_periods = _build_common_inputs(
        config,
        historical_incidents,
    )
    replay_incidents = [
        incident
        for incident in historical_incidents
        if incident.occurred_at.date() == config.scenario.replay_date
    ]
    if not replay_incidents:
        raise ValueError(
            f"No incidents exist on replay date {config.scenario.replay_date.isoformat()}"
        )

    planning_incidents: List[PlanningIncident] = []
    for index, incident in enumerate(replay_incidents):
        classification = classify_incident(incident.incident_type)
        planning_incidents.append(
            PlanningIncident(
                request_id=f"IR-{index + 1:04d}",
                source_id=incident.source_id,
                period=period_for_datetime(
                    incident.occurred_at,
                    config.time.period_minutes,
                ),
                region_id=grid.region_id_for(
                    incident.latitude,
                    incident.longitude,
                ),
                category=classification.category,
                response_limit_periods=classification.response_limit_periods,
                latitude=incident.latitude,
                longitude=incident.longitude,
            )
        )

    return _build_scenario(
        config,
        historical_incidents,
        grid,
        planning_incidents,
        vfop,
        travel_periods,
        {
            "replay_date": config.scenario.replay_date.isoformat(),
            "incident_generation": "observed historical-day replay",
        },
    )


def build_poisson_scenario(
    config: AppConfig,
    historical_incidents: List[HistoricalIncident],
) -> ScenarioBuildResult:
    grid, vfop, travel_periods = _build_common_inputs(
        config,
        historical_incidents,
    )
    history_days = (config.data.history_end - config.data.history_start).days + 1
    poisson_rates = learn_poisson_rates(
        historical_incidents,
        grid,
        history_days=history_days,
        period_minutes=config.time.period_minutes,
    )
    planning_incidents = sample_poisson_incidents(
        poisson_rates,
        grid,
        random_seed=config.scenario.random_seed,
        rate_scale=config.scenario.poisson_rate_scale,
    )
    expected_incident_count = sum(
        rate.daily_rate for rate in poisson_rates
    ) * config.scenario.poisson_rate_scale

    return _build_scenario(
        config,
        historical_incidents,
        grid,
        planning_incidents,
        vfop,
        travel_periods,
        {
            "generation_date": config.scenario.replay_date.isoformat(),
            "incident_generation": "independent Poisson bucket sampling",
            "poisson_history_days": history_days,
            "poisson_rate_scale": config.scenario.poisson_rate_scale,
            "poisson_expected_incident_count": round(expected_incident_count, 6),
            "random_seed": config.scenario.random_seed,
            "nonzero_rate_buckets": len(poisson_rates),
        },
        poisson_rates=poisson_rates,
    )


def build_scenario(
    config: AppConfig,
    historical_incidents: List[HistoricalIncident],
) -> ScenarioBuildResult:
    if config.scenario.mode == "replay":
        return build_replay_scenario(config, historical_incidents)
    if config.scenario.mode == "poisson":
        return build_poisson_scenario(config, historical_incidents)
    raise ValueError(f"Unsupported scenario mode: {config.scenario.mode}")
