from datetime import datetime

from patrol_planning.time.periods import period_for_datetime, period_label


def test_period_conversion_for_thirty_minute_periods() -> None:
    assert period_for_datetime(datetime(2023, 1, 1, 0, 0), 30) == 0
    assert period_for_datetime(datetime(2023, 1, 1, 8, 45), 30) == 17
    assert period_for_datetime(datetime(2023, 1, 1, 23, 59), 30) == 47
    assert period_label(17, 30) == "08:30"
