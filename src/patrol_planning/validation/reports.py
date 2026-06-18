from dataclasses import asdict, dataclass
from typing import Dict


@dataclass
class DataValidationReport:
    source_rows: int = 0
    selected_rows: int = 0
    output_rows: int = 0
    invalid_dates: int = 0
    invalid_times: int = 0
    invalid_coordinates: int = 0
    duplicate_ids: int = 0

    def to_dict(self) -> Dict[str, int]:
        return asdict(self)
