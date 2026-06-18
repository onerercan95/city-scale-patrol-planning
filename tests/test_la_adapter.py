from datetime import date
from pathlib import Path

from patrol_planning.config.models import DataConfig
from patrol_planning.data.adapters.la_crime import LACrimeAdapter


def test_la_adapter_filters_and_normalizes(tmp_path: Path) -> None:
    csv_path = tmp_path / "la.csv"
    csv_path.write_text(
        "DR_NO,DATE OCC,TIME OCC,AREA NAME,Crm Cd Desc,LAT,LON\n"
        "1,01/15/2023 12:00:00 AM,0845,Central,ROBBERY,34.05,-118.25\n"
        "2,01/15/2023 12:00:00 AM,0900,Pacific,THEFT,34.01,-118.40\n"
        "3,01/15/2023 12:00:00 AM,0915,Central,THEFT,0,0\n",
        encoding="utf-8",
    )
    config = DataConfig(
        csv_path=csv_path,
        area_name="Central",
        history_start=date(2023, 1, 1),
        history_end=date(2023, 1, 31),
        chunk_size=1000,
    )

    incidents, report = LACrimeAdapter(config).load()

    assert len(incidents) == 1
    assert incidents[0].occurred_at.hour == 8
    assert incidents[0].occurred_at.minute == 45
    assert report.source_rows == 3
    assert report.selected_rows == 2
    assert report.invalid_coordinates == 1
