from datetime import datetime


def period_for_datetime(value: datetime, period_minutes: int) -> int:
    minutes_after_midnight = value.hour * 60 + value.minute
    return minutes_after_midnight // period_minutes


def period_label(period: int, period_minutes: int) -> str:
    total_minutes = period * period_minutes
    hour, minute = divmod(total_minutes, 60)
    return f"{hour:02d}:{minute:02d}"
