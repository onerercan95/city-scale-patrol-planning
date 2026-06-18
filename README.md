# City-Scale Patrol Planning

Offline police patrol planning using historical Los Angeles crime data. The
program runs the MinP, MaxP, and grafting stages and generates route data,
images, validation reports, and interactive maps.

## Requirements

- Python 3.9 or newer

## Dataset

Download the public City of Los Angeles crime dataset:

```bash
python3 scripts/download_dataset.py
```

The file will be saved as:

```text
data/LA_Crime_Data_from_2020_to_2024.csv
```

The CSV is downloaded from the official Los Angeles Open Data portal. It is not
stored directly in Git because its size is larger than GitHub's file limit.

## Installation

From the project folder, install the program and its dependencies:

```bash
python3 -m pip install --user -e ".[dev]"
```

On macOS, if the `patrol` command is not found, add the user Python command
folder to your shell:

```bash
echo 'export PATH="$HOME/Library/Python/3.9/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

## Run

The default configuration is selected in `configs/default.yaml`.

Run the complete planning pipeline:

```bash
patrol run
```

Use a specific configuration when needed:

```bash
patrol run --config configs/la_central_january_2023.yaml
```

## Configuration

The default configuration is selected in:

```text
configs/default.yaml
```

The main Poisson configuration is:

```text
configs/la_central_poisson.yaml
```

### Dataset Selection

```yaml
data:
  csv_path: "data/LA_Crime_Data_from_2020_to_2024.csv"
  area_name: "Central"
  history_start: "2022-01-01"
  history_end: "2023-01-01"
```

- `csv_path` is the location of the crime dataset.
- `area_name` selects the LAPD area used by the program.
- `history_start` and `history_end` define the historical interval used for
  filtering records, calculating the VFoP proxy, and learning Poisson incident
  rates.
- The selected interval must be inside the available dataset interval.
- The current dataset contains records from `2020-01-01` to `2024-12-30`.

### Scenario Mode

```yaml
scenario:
  mode: "poisson"
  replay_date: "2023-01-01"
  officers: 60
  random_seed: 42
  poisson_rate_scale: 1.0
```

The program supports `replay` and `poisson` modes.

#### Replay Mode

```yaml
mode: "replay"
```

Replay mode uses the incidents that occurred on `replay_date`.

The selected day:

- Must be between `history_start` and `history_end`.
- Must be inside the dataset interval from `2020-01-01` to `2024-12-30`.
- Must contain valid incidents after area, time, and coordinate filtering.

#### Poisson Mode

```yaml
mode: "poisson"
```

Poisson mode learns incident rates from the complete historical interval and
generates a possible planning day.

- `random_seed` controls the generated incidents.
- The same seed and configuration produce the same scenario.
- Different seeds can produce different incident locations, periods, and
  categories.
- `poisson_rate_scale: 1.0` uses the learned daily rates.
- `poisson_rate_scale: 2.0` produces approximately twice as many incidents.
- `poisson_rate_scale: 0.5` produces approximately half as many incidents.
- In Poisson mode, `replay_date` is used as the generated planning-day label.
  It must still be inside the configured historical interval.

### Officer Count

```yaml
officers: 60
```

This is the total number of available officers. MinP selects the officers
required for incident coverage and MaxP receives the remaining officers. If the
count is too low, MinP may report that the scenario is infeasible. Increasing
the count generally allows the final plan to achieve more visibility.

### Grid Size

```yaml
grid:
  rows: 20
  columns: 20
```

The selected geographic area is divided into grid cells.

- A `20 x 20` grid creates 400 patrol regions.
- A larger grid provides more geographic detail.
- A larger grid also increases the planning and network-flow workload.
- Grid cells represent geographic areas rather than individual streets.

### Time Configuration

```yaml
time:
  period_minutes: 30
  shifts_per_day: 3
```

- `period_minutes` defines the length of one planning period.
- `shifts_per_day` defines the number of shifts in one day.
- With 30-minute periods, one day contains 48 periods.
- With three shifts, each shift contains 16 periods or eight hours.
- `1440` must be divisible by `period_minutes`.
- The number of daily periods must be divisible by `shifts_per_day`.
- Smaller periods provide more time detail but increase solver workload.

### Travel Configuration

```yaml
travel:
  periods_per_grid_step: 1
```

This controls the travel time between neighboring grid cells.

- Moving to a neighboring cell takes one planning period.
- With 30-minute periods, one grid step represents 30 minutes of travel.
- Travel currently uses Manhattan grid distance rather than real road-network
  travel time.

Generated files are written under `artifacts/`:

```text
artifacts/<run>/
├── data/    CSV and JSON results
├── images/  Generated charts and heatmaps
└── html/    Interactive patrol maps
```

The `images/` folder includes the run summary, PVR stage comparison, officer
allocation, incident coverage, grafting evaluation, and VFoP heatmaps.

## Tests

```bash
pytest
```

## Zenodo
[![DOI](https://zenodo.org/badge/1273650915.svg)](https://doi.org/10.5281/zenodo.20752224)
