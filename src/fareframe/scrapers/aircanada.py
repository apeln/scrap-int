from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re

from fareframe.core.base import BaseScraper
from fareframe.core.registry import register_scraper
from fareframe.models import FlightOffer, SearchRequest
from fareframe.settings import get_settings

def _validate_iso_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be in YYYY-MM-DD format") from exc


def _find_browser_executable() -> str:
    candidates = tuple(Path(path) for path in get_settings().browser.browser_executables)
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    known_locations = ", ".join(str(path) for path in candidates)
    raise RuntimeError(f"Could not find Chrome or Edge. Checked: {known_locations}")


@dataclass(slots=True)
class _AirCanadaSearchResult:
    url: str
    status: str
    notes: str
    offers: list[FlightOffer]


@register_scraper("aircanada")
class AirCanadaScraper(BaseScraper):
    def search(self, request: SearchRequest) -> list[FlightOffer]:
        if not request.return_date:
            raise ValueError("Air Canada round-trip search requires --return-date")

        departure_date = _validate_iso_date(request.date, "date")
        return_date = _validate_iso_date(request.return_date, "return-date")
        if return_date < departure_date:
            raise ValueError("return-date must be on or after date")

        result = self._run_live_search(
            origin=request.origin.strip(),
            destination=request.destination.strip(),
            departure_date=departure_date,
            return_date=return_date,
        )
        if result.offers:
            return result.offers
        return [
            FlightOffer(
                site=self.site_name,
                origin=request.origin.strip(),
                destination=request.destination.strip(),
                date=departure_date.isoformat(),
                price_text=result.status,
                currency="CAD",
                deep_link=result.url,
                notes=result.notes,
            )
        ]

    def _run_live_search(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: date,
    ) -> _AirCanadaSearchResult:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Playwright is required for the Air Canada scraper") from exc

        browser_path = _find_browser_executable()
        settings = get_settings()
        browser_settings = settings.browser

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=browser_settings.headless,
                executable_path=browser_path,
            )
            page = browser.new_page(
                viewport={
                    "width": browser_settings.viewport_width,
                    "height": browser_settings.viewport_height,
                }
            )
            try:
                page.goto(
                    settings.sites.aircanada_url,
                    wait_until="domcontentloaded",
                    timeout=browser_settings.page_load_timeout_ms,
                )
                page.wait_for_timeout(browser_settings.initial_page_wait_ms)

                accept_button = page.get_by_role("button", name="Accept all")
                if accept_button.count():
                    accept_button.first.click()
                    page.wait_for_timeout(browser_settings.confirm_wait_ms)

                self._ensure_round_trip(page)
                self._select_airport(page, "origin", origin)
                self._select_airport(page, "destination", destination)
                self._fill_roundtrip_dates(page, departure_date, return_date)

                page.locator("#bkmg-desktop_findButton").click(force=True)
                self._wait_for_results_page(page)

                current_url = page.url
                page_text = page.locator("body").inner_text()
            finally:
                browser.close()

        offers = self._extract_offers(
            page_text=page_text,
            fallback_origin=origin,
            fallback_destination=destination,
            fallback_date=departure_date.isoformat(),
            deep_link=current_url,
        )
        if offers:
            return _AirCanadaSearchResult(
                url=current_url,
                status="Results loaded",
                notes="Loaded Air Canada availability results and extracted outbound flights.",
                offers=offers,
            )

        return _AirCanadaSearchResult(
            url=current_url,
            status="Browser automation completed",
            notes="Opened Air Canada, filled destination and round-trip dates, and clicked Search.",
            offers=[],
        )

    def _ensure_round_trip(self, page) -> None:
        browser_settings = get_settings().browser
        trip_toggle = page.locator("#bkmgFlights-trip-selector_tripTypeBtn")
        if "Round-trip" in trip_toggle.inner_text():
            return
        trip_toggle.click()
        page.wait_for_timeout(browser_settings.short_wait_ms)
        page.get_by_text("Round-trip", exact=True).click(force=True)
        page.wait_for_timeout(browser_settings.confirm_wait_ms)

    def _select_airport(self, page, field: str, value: str) -> None:
        browser_settings = get_settings().browser
        mapping = {
            "origin": (
                "#flightsOriginLocationbkmgLocationContainer",
                'input[name="flightsOriginLocation"]:visible',
                "#dynamicLocationFormflightsOriginLocation",
            ),
            "destination": (
                "#flightsOriginDestinationbkmgLocationContainer",
                'input[name="flightsOriginDestination"]:visible',
                "#dynamicLocationFormflightsOriginDestination",
            ),
        }
        container_selector, input_selector, form_selector = mapping[field]
        page.locator(container_selector).click()
        page.wait_for_timeout(browser_settings.short_wait_ms)
        input_locator = page.locator(input_selector).first
        input_locator.wait_for(state="visible")
        input_locator.click(force=True)
        input_locator.evaluate(
            """(element, airportValue) => {
                element.value = "";
                element.dispatchEvent(new Event("input", { bubbles: true }));
                element.value = airportValue;
                element.dispatchEvent(new Event("input", { bubbles: true }));
                element.dispatchEvent(new Event("change", { bubbles: true }));
            }""",
            value,
        )
        page.wait_for_timeout(browser_settings.suggestion_wait_ms)
        option_locator = page.locator(f'{form_selector} [role="option"]', has_text=value).first
        if option_locator.count() == 0:
            raise RuntimeError(f"Air Canada did not show any {field} airport suggestions for '{value}'")
        option_locator.evaluate("(e) => e.click()")
        page.wait_for_timeout(browser_settings.confirm_wait_ms)

    def _fill_roundtrip_dates(self, page, departure_date: date, return_date: date) -> None:
        browser_settings = get_settings().browser
        page.locator('input[name="bkmg-desktop_travelDates-formfield-1"]').fill(
            departure_date.strftime("%d/%m")
        )
        page.wait_for_timeout(browser_settings.short_wait_ms)
        page.locator('input[name="bkmg-desktop_travelDates-formfield-2"]').fill(
            return_date.strftime("%d/%m")
        )
        page.wait_for_timeout(browser_settings.short_wait_ms)

    def _wait_for_results_page(self, page) -> None:
        browser_settings = get_settings().browser
        timeout_ms = browser_settings.post_search_wait_ms
        page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
        page.wait_for_function(
            """
            () => {
                const href = window.location.href;
                const bodyText = document.body ? document.body.innerText : "";
                return (
                    href.includes("/availability/") ||
                    href.includes("/no-flights-found") ||
                    bodyText.includes("Flight results") ||
                    /\\$\\d[\\d,]*/.test(bodyText)
                );
            }
            """,
            timeout=timeout_ms,
        )

        if "/availability/" not in page.url:
            return

        page.wait_for_function(
            """
            () => {
                const bodyText = document.body ? document.body.innerText : "";
                return bodyText.includes("Flight results") || /\\$\\d[\\d,]*/.test(bodyText);
            }
            """,
            timeout=timeout_ms,
        )
        page.wait_for_timeout(browser_settings.results_settle_wait_ms)

    def _extract_offers(
        self,
        page_text: str,
        fallback_origin: str,
        fallback_destination: str,
        fallback_date: str,
        deep_link: str,
    ) -> list[FlightOffer]:
        if "Flight results" not in page_text:
            return []

        chunks = re.split(r"(?:Lowest price\s+)?Flight departing from ", page_text)
        offers: list[FlightOffer] = []
        for chunk in chunks[1:]:
            offer = self._parse_offer_chunk(
                chunk=chunk,
                fallback_origin=fallback_origin,
                fallback_destination=fallback_destination,
                fallback_date=fallback_date,
                deep_link=deep_link,
            )
            if offer is not None:
                offers.append(offer)
        return offers

    def _parse_offer_chunk(
        self,
        chunk: str,
        fallback_origin: str,
        fallback_destination: str,
        fallback_date: str,
        deep_link: str,
    ) -> FlightOffer | None:
        lines = [line.strip() for line in chunk.splitlines() if line.strip()]
        if not lines:
            return None

        header_match = re.match(
            r"(?P<origin_city>.+?) (?P<origin_code>[A-Z]{3}) at (?P<dep_time>\d{1,2}:\d{2}) "
            r"and arriving in (?P<dest_city>.+?) (?P<dest_code>[A-Z]{3}) at (?P<arr_time>\d{1,2}:\d{2})"
            r"(?: on (?P<flight_date>.+))?",
            lines[0],
        )
        if not header_match:
            return None

        stops_match = re.search(r"\b(\d+\s+stop(?:s)?)\b", chunk)
        duration_match = re.search(r"\b(\d+h(?:\s+\d+m)?|\d+m)\b", chunk)
        price_matches = re.findall(r"\$([\d,]+)", chunk)
        if not price_matches:
            return None

        economy_price = f"${price_matches[0]}"
        business_price = f"${price_matches[1]}" if len(price_matches) > 1 else None
        notes_parts = [
            f"Dep {header_match.group('dep_time')}",
            f"Arr {header_match.group('arr_time')}",
        ]
        if stops_match:
            notes_parts.append(stops_match.group(1))
        if duration_match:
            notes_parts.append(duration_match.group(1))
        if business_price:
            notes_parts.append(f"Business {business_price}")

        return FlightOffer(
            site=self.site_name,
            origin=header_match.group("origin_code") or fallback_origin,
            destination=header_match.group("dest_code") or fallback_destination,
            date=fallback_date,
            price_text=economy_price,
            currency="CAD",
            deep_link=deep_link,
            notes="; ".join(notes_parts),
        )
