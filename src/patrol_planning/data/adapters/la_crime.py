from __future__ import annotations

from datetime import datetime, time
from typing import List, Set, Tuple

import pandas as pd

from patrol_planning.config.models import DataConfig
from patrol_planning.domain.models import HistoricalIncident
from patrol_planning.validation.reports import DataValidationReport


REQUIRED_COLUMNS = {
    "DR_NO",
    "DATE OCC",
    "TIME OCC",
    "AREA NAME",
    "Crm Cd Desc",
    "LAT",
    "LON",
}


class LACrimeAdapter:
    """Translate the public LAPD CSV schema into project domain objects."""

    def __init__(self, config: DataConfig) -> None:
        self.config = config

    def load(self) -> Tuple[List[HistoricalIncident], DataValidationReport]:
        if not self.config.csv_path.exists():
            raise FileNotFoundError(f"LA crime CSV not found: {self.config.csv_path}")

        header = set(pd.read_csv(self.config.csv_path, nrows=0).columns)
        missing = REQUIRED_COLUMNS - header
        if missing:
            raise ValueError(f"LA crime CSV is missing required columns: {sorted(missing)}")

        incidents: List[HistoricalIncident] = []
        seen_ids: Set[int] = set()
        report = DataValidationReport()
        usecols = sorted(REQUIRED_COLUMNS)

        for chunk in pd.read_csv(
            self.config.csv_path,
            usecols=usecols,
            chunksize=self.config.chunk_size,
            low_memory=False,
        ):
            report.source_rows += len(chunk)
            dates = pd.to_datetime(
                chunk["DATE OCC"],
                format="%m/%d/%Y %I:%M:%S %p",
                errors="coerce",
            )
            area_mask = chunk["AREA NAME"].eq(self.config.area_name)
            date_mask = dates.dt.date.between(
                self.config.history_start,
                self.config.history_end,
            )
            selected = chunk.loc[area_mask & date_mask].copy()
            selected_dates = dates.loc[selected.index]
            report.selected_rows += len(selected)

            for row_index, row in selected.iterrows():
                source_id = int(row["DR_NO"])
                latitude = float(row["LAT"])
                longitude = float(row["LON"])
                occurrence_date = selected_dates.loc[row_index]
                hhmm = int(row["TIME OCC"])

                if pd.isna(occurrence_date):
                    report.invalid_dates += 1
                    continue
                if not (33.0 <= latitude <= 35.0 and -119.0 <= longitude <= -117.0):
                    report.invalid_coordinates += 1
                    continue
                if source_id in seen_ids:
                    report.duplicate_ids += 1
                    continue

                hour, minute = divmod(hhmm, 100)
                if hour > 23 or minute > 59:
                    report.invalid_times += 1
                    continue

                seen_ids.add(source_id)
                occurred_at = datetime.combine(
                    occurrence_date.date(),
                    time(hour=hour, minute=minute),
                )
                incidents.append(
                    HistoricalIncident(
                        source_id=source_id,
                        occurred_at=occurred_at,
                        latitude=latitude,
                        longitude=longitude,
                        incident_type=str(row["Crm Cd Desc"]).strip(),
                        area_name=str(row["AREA NAME"]).strip(),
                    )
                )

        incidents.sort(key=lambda incident: (incident.occurred_at, incident.source_id))
        report.output_rows = len(incidents)
        return incidents, report
