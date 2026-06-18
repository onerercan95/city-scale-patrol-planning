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

Generated files are written under `artifacts/`:

```text
artifacts/<run>/
├── data/    CSV and JSON results
├── images/  Generated charts and heatmaps
└── html/    Interactive patrol maps
```

## Tests

```bash
pytest
```
