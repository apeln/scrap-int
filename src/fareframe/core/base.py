from __future__ import annotations

from abc import ABC, abstractmethod

from fareframe.models import FlightOffer, SearchRequest


class BaseScraper(ABC):
    site_name: str

    @abstractmethod
    def search(self, request: SearchRequest) -> list[FlightOffer]:
        """Return normalized offers for a site-specific search request."""
