from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class IncidentClassification:
    category: str
    response_limit_periods: int


URGENT_KEYWORDS: Tuple[str, ...] = (
    "HOMICIDE",
    "ROBBERY",
    "ASSAULT",
    "BATTERY",
    "SHOTS FIRED",
    "WEAPON",
    "KIDNAPPING",
    "RAPE",
)
PROPERTY_KEYWORDS: Tuple[str, ...] = (
    "BURGLARY",
    "STOLEN",
    "VEHICLE",
)
THEFT_KEYWORDS: Tuple[str, ...] = (
    "THEFT",
    "SHOPLIFTING",
    "BUNCO",
)
DISORDER_KEYWORDS: Tuple[str, ...] = (
    "VANDALISM",
    "TRESPASSING",
    "THREATS",
    "RESTRAINING ORDER",
    "COURT ORDER",
)


def classify_incident(description: str) -> IncidentClassification:
    normalized = description.upper()
    if any(keyword in normalized for keyword in URGENT_KEYWORDS):
        return IncidentClassification("urgent", 0)
    if any(keyword in normalized for keyword in PROPERTY_KEYWORDS):
        return IncidentClassification("property", 1)
    if any(keyword in normalized for keyword in THEFT_KEYWORDS):
        return IncidentClassification("theft", 2)
    if any(keyword in normalized for keyword in DISORDER_KEYWORDS):
        return IncidentClassification("public_disorder", 2)
    return IncidentClassification("other", 2)


RESPONSE_LIMITS_BY_CATEGORY = {
    "urgent": 0,
    "property": 1,
    "theft": 2,
    "public_disorder": 2,
    "other": 2,
}


def response_limit_for_category(category: str) -> int:
    try:
        return RESPONSE_LIMITS_BY_CATEGORY[category]
    except KeyError as error:
        raise ValueError(f"Unknown incident category: {category}") from error
