from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SearchRequest:
    site: str
    origin: str
    destination: str
    date: str
    return_date: str | None = None


@dataclass(slots=True)
class FlightOffer:
    site: str
    origin: str
    destination: str
    date: str
    price_text: str
    currency: str | None
    deep_link: str
    notes: str = ""
