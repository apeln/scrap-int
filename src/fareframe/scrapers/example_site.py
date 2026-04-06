from __future__ import annotations

from fareframe.core.base import BaseScraper
from fareframe.core.registry import register_scraper
from fareframe.models import FlightOffer, SearchRequest


@register_scraper("example-site")
class ExampleSiteScraper(BaseScraper):
    def search(self, request: SearchRequest) -> list[FlightOffer]:
        return [
            FlightOffer(
                site=self.site_name,
                origin=request.origin,
                destination=request.destination,
                date=request.date,
                price_text="$199",
                currency="USD",
                deep_link=(
                    "https://example.com/flights"
                    f"?origin={request.origin}&destination={request.destination}&date={request.date}"
                ),
                notes="Placeholder scraper. Replace with real fetching and parsing logic.",
            )
        ]
