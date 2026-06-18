from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import List, Literal

import yaml
from pydantic import BaseModel, Field, model_validator


class DataConfig(BaseModel):
    csv_path: Path
    area_name: str
    history_start: date
    history_end: date
    chunk_size: int = Field(default=100_000, ge=1_000)


class GridConfig(BaseModel):
    rows: int = Field(default=12, ge=2)
    columns: int = Field(default=12, ge=2)


class TimeConfig(BaseModel):
    period_minutes: int = Field(default=30, ge=5, le=480)
    shifts_per_day: int = Field(default=3, ge=1)

    @model_validator(mode="after")
    def validate_periods(self) -> "TimeConfig":
        if 1440 % self.period_minutes != 0:
            raise ValueError("period_minutes must divide evenly into 24 hours")
        if self.periods_per_day % self.shifts_per_day != 0:
            raise ValueError("shifts_per_day must divide the number of daily periods")
        return self

    @property
    def periods_per_day(self) -> int:
        return 1440 // self.period_minutes

    @property
    def periods_per_shift(self) -> int:
        return self.periods_per_day // self.shifts_per_day


class ScenarioConfig(BaseModel):
    mode: Literal["replay", "poisson"] = "replay"
    replay_date: date
    officers: int = Field(default=30, ge=1)
    random_seed: int = 42
    poisson_rate_scale: float = Field(default=1.0, gt=0.0)


class VFoPConfig(BaseModel):
    baseline: float = Field(default=0.05, ge=0.0, le=1.0)


class TravelConfig(BaseModel):
    periods_per_grid_step: int = Field(default=1, ge=1)


class MinPConfig(BaseModel):
    max_labels: int = Field(default=8_000, ge=100)


class MaxPConfig(BaseModel):
    cost_scale: int = Field(default=10_000, ge=100)


class ExperimentConfig(BaseModel):
    replay_dates: List[date] = Field(default_factory=list)
    officer_counts: List[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_values(self) -> "ExperimentConfig":
        if any(count < 1 for count in self.officer_counts):
            raise ValueError("experiment officer counts must be positive")
        if len(set(self.replay_dates)) != len(self.replay_dates):
            raise ValueError("experiment replay dates must be unique")
        if len(set(self.officer_counts)) != len(self.officer_counts):
            raise ValueError("experiment officer counts must be unique")
        return self


class ComparisonConfig(BaseModel):
    seeds: List[int] = Field(default_factory=lambda: [40, 41, 42, 43, 44])
    officer_counts: List[int] = Field(default_factory=lambda: [20, 30, 40])

    @model_validator(mode="after")
    def validate_values(self) -> "ComparisonConfig":
        if any(count < 1 for count in self.officer_counts):
            raise ValueError("comparison officer counts must be positive")
        if len(set(self.seeds)) != len(self.seeds):
            raise ValueError("comparison seeds must be unique")
        if len(set(self.officer_counts)) != len(self.officer_counts):
            raise ValueError("comparison officer counts must be unique")
        return self


class EvaluationGridConfig(BaseModel):
    rows: int = Field(ge=2)
    columns: int = Field(ge=2)


class FinalEvaluationConfig(BaseModel):
    seeds: List[int] = Field(
        default_factory=lambda: list(range(40, 50))
    )
    officer_counts: List[int] = Field(
        default_factory=lambda: [10, 12, 14, 16, 18, 20, 25, 30, 40]
    )
    grids: List[EvaluationGridConfig] = Field(
        default_factory=lambda: [
            EvaluationGridConfig(rows=10, columns=10),
            EvaluationGridConfig(rows=12, columns=12),
            EvaluationGridConfig(rows=15, columns=15),
        ]
    )
    non_primary_seed_limit: int = Field(default=5, ge=1)

    @model_validator(mode="after")
    def validate_values(self) -> "FinalEvaluationConfig":
        if any(count < 1 for count in self.officer_counts):
            raise ValueError("final evaluation officer counts must be positive")
        if len(set(self.seeds)) != len(self.seeds):
            raise ValueError("final evaluation seeds must be unique")
        if len(set(self.officer_counts)) != len(self.officer_counts):
            raise ValueError("final evaluation officer counts must be unique")
        grid_keys = [(grid.rows, grid.columns) for grid in self.grids]
        if len(set(grid_keys)) != len(grid_keys):
            raise ValueError("final evaluation grids must be unique")
        return self


class OutputConfig(BaseModel):
    directory: Path = Path("artifacts/la_central")


class AppConfig(BaseModel):
    run_name: str
    data: DataConfig
    grid: GridConfig = Field(default_factory=GridConfig)
    time: TimeConfig = Field(default_factory=TimeConfig)
    scenario: ScenarioConfig
    vfop: VFoPConfig = Field(default_factory=VFoPConfig)
    travel: TravelConfig = Field(default_factory=TravelConfig)
    minp: MinPConfig = Field(default_factory=MinPConfig)
    maxp: MaxPConfig = Field(default_factory=MaxPConfig)
    experiment: ExperimentConfig = Field(default_factory=ExperimentConfig)
    comparison: ComparisonConfig = Field(default_factory=ComparisonConfig)
    final_evaluation: FinalEvaluationConfig = Field(
        default_factory=FinalEvaluationConfig
    )
    output: OutputConfig = Field(default_factory=OutputConfig)

    @model_validator(mode="after")
    def validate_dates(self) -> "AppConfig":
        if self.data.history_start > self.data.history_end:
            raise ValueError("history_start must not be after history_end")
        if not self.data.history_start <= self.scenario.replay_date <= self.data.history_end:
            raise ValueError("replay_date must be inside the historical date range")
        if any(
            not self.data.history_start <= replay_date <= self.data.history_end
            for replay_date in self.experiment.replay_dates
        ):
            raise ValueError("all experiment replay dates must be inside history range")
        return self


def load_config(path: Path) -> AppConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    config = AppConfig.model_validate(payload)

    if not config.data.csv_path.is_absolute():
        project_relative = Path.cwd() / config.data.csv_path
        config.data.csv_path = project_relative.resolve()
    if not config.output.directory.is_absolute():
        config.output.directory = (Path.cwd() / config.output.directory).resolve()
    return config
