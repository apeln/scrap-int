from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from fareframe.core.base import BaseScraper
from fareframe.core.registry import register_scraper
from fareframe.models import FlightOffer, SearchRequest
from fareframe.settings import get_settings


def _validate_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("date must be in YYYY-MM-DD format") from exc


def _find_browser_executable() -> str:
    candidates = tuple(Path(path) for path in get_settings().browser.browser_executables)
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    known_locations = ", ".join(str(path) for path in candidates)
    raise RuntimeError(f"Could not find Chrome or Edge. Checked: {known_locations}")


@dataclass(slots=True)
class _WestJetSearchResult:
    url: str
    status: str
    notes: str
    offers: list[FlightOffer]


@register_scraper("westjet")
class WestJetScraper(BaseScraper):
    def search(self, request: SearchRequest) -> list[FlightOffer]:
        travel_date = _validate_iso_date(request.date)
        result = self._run_live_search(
            origin=request.origin.strip(),
            destination=request.destination.strip(),
            travel_date=travel_date,
        )
        if result.offers:
            return result.offers
        return [
            FlightOffer(
                site=self.site_name,
                origin=request.origin.strip(),
                destination=request.destination.strip(),
                date=travel_date.isoformat(),
                price_text=result.status,
                currency="CAD",
                deep_link=result.url,
                notes=result.notes,
            )
        ]

    def _run_live_search(self, origin: str, destination: str, travel_date: date) -> _WestJetSearchResult:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Playwright is required for the WestJet scraper") from exc

        browser_path = _find_browser_executable()
        date_key = f"{travel_date.year}-{travel_date.month}-{travel_date.day}"
        api_response: dict | list | None = None
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
                def on_response(response) -> None:
                    nonlocal api_response
                    if api_response is not None:
                        return
                    if "apiw.westjet.com/ecomm/booktrip/flight-search-api/v1" not in response.url:
                        return
                    if response.status != 200:
                        return
                    try:
                        api_response = response.json()
                    except Exception:
                        return

                page.on("response", on_response)
                page.goto(
                    settings.sites.westjet_url,
                    wait_until="domcontentloaded",
                    timeout=browser_settings.page_load_timeout_ms,
                )
                page.wait_for_timeout(browser_settings.initial_page_wait_ms)

                accept_button = page.get_by_role("button", name="Accept")
                if accept_button.count():
                    accept_button.click()
                    page.wait_for_timeout(browser_settings.confirm_wait_ms)

                self._choose_one_way(page)
                self._select_airport(page, "destination", destination)

                if origin and origin.casefold() != page.locator('input[name="origin-airport-0"]').input_value().strip().casefold():
                    self._select_airport(page, "origin", origin)

                page.locator('input[name="departure-date-0"]').click()
                page.wait_for_timeout(browser_settings.short_wait_ms)
                page.locator(f'[data-full="{date_key}"]:visible').click()
                page.wait_for_timeout(browser_settings.suggestion_wait_ms)

                page.locator('[data-qa="widget-book-submit"]').click()
                try:
                    page.wait_for_url("**/shop/flight/**", timeout=browser_settings.post_search_wait_ms)
                except PlaywrightTimeoutError:
                    page.wait_for_timeout(browser_settings.confirm_wait_ms * 5)

                current_url = page.url
                page_text = page.locator("body").inner_text()
            finally:
                browser.close()

        if api_response is not None:
            offers = self._extract_offers(
                payload=api_response,
                fallback_origin=origin,
                fallback_destination=destination,
                fallback_date=travel_date.isoformat(),
                deep_link=current_url,
            )
            if offers:
                return _WestJetSearchResult(
                    url=current_url,
                    status="Results page loaded",
                    notes="WestJet generated a live shop/flight results URL.",
                    offers=offers,
                )

        if "/shop/flight/" in current_url:
            return _WestJetSearchResult(
                url=current_url,
                status="Results page loaded",
                notes="WestJet generated a live shop/flight results URL.",
                offers=[],
            )

        if "NO_FLIGHTS_FOUND" in current_url or "No flights were found." in page_text:
            return _WestJetSearchResult(
                url=current_url,
                status="No flights found",
                notes="WestJet completed the search but returned no live flight results for these inputs.",
                offers=[],
            )

        return _WestJetSearchResult(
            url=current_url,
            status="Search submitted",
            notes="WestJet accepted the search flow, but a live shop/flight results URL was not exposed in this session.",
            offers=[],
        )

    def _choose_one_way(self, page) -> None:
        browser_settings = get_settings().browser
        page.locator('input[name="trip-type-selector"]').click()
        page.wait_for_timeout(browser_settings.short_wait_ms)
        page.locator("label").filter(
            has=page.locator("span.radio-label", has_text="One way")
        ).click()
        page.wait_for_timeout(browser_settings.confirm_wait_ms)

    def _select_airport(self, page, field: str, value: str) -> None:
        browser_settings = get_settings().browser
        input_name = f"{field}-airport-0"
        container_class = f".{field}-input"
        input_locator = page.locator(f'input[name="{input_name}"]')
        input_locator.click()
        input_locator.press("Control+A")
        input_locator.fill(value)
        page.wait_for_timeout(browser_settings.suggestion_wait_ms)

        option_locator = page.locator(f"{container_class} .list-option-airport:visible").first
        if option_locator.count() == 0:
            raise RuntimeError(f"WestJet did not show any {field} airport suggestions for '{value}'")
        option_locator.click()
        page.wait_for_timeout(browser_settings.confirm_wait_ms)

    def _extract_offers(
        self,
        payload: dict | list,
        fallback_origin: str,
        fallback_destination: str,
        fallback_date: str,
        deep_link: str,
    ) -> list[FlightOffer]:
        flights = self._find_candidate_flights(payload)
        offers = []
        for flight in flights:
            if not isinstance(flight, dict):
                continue

            origin = self._pick_value(
                flight,
                [
                    "origin",
                    "departure",
                    "departureAirportCode",
                ],
            ) or fallback_origin
            destination = self._pick_value(
                flight,
                [
                    "destination",
                    "arrival",
                    "arrivalAirportCode",
                ],
            ) or fallback_destination
            flight_date = self._pick_value(
                flight,
                [
                    "departureDate",
                    "date",
                ],
            ) or fallback_date
            price_text = self._extract_price_text(flight) or "Price unavailable"
            currency = self._pick_value(
                flight,
                [
                    "currency",
                    "currencyCode",
                ],
            ) or "CAD"
            notes = self._build_notes(flight)

            offers.append(
                FlightOffer(
                    site=self.site_name,
                    origin=str(origin),
                    destination=str(destination),
                    date=str(flight_date),
                    price_text=price_text,
                    currency=str(currency),
                    deep_link=deep_link,
                    notes=notes,
                )
            )
        return offers

    def _find_candidate_flights(self, payload: dict | list) -> list[dict]:
        candidate_keys = (
            "flights",
            "flightOptions",
            "options",
            "itineraries",
            "journeys",
            "outbounds",
            "results",
        )
        stack = [payload]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                for key, value in current.items():
                    if key in candidate_keys and isinstance(value, list) and value and isinstance(value[0], dict):
                        return value
                    stack.append(value)
            elif isinstance(current, list):
                stack.extend(current)
        return []

    def _pick_value(self, payload: dict, keys: list[str]) -> str | None:
        stack = [payload]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                for key, value in current.items():
                    if key in keys and isinstance(value, (str, int, float)):
                        return str(value)
                    stack.append(value)
            elif isinstance(current, list):
                stack.extend(current)
        return None

    def _extract_price_text(self, payload: dict) -> str | None:
        stack = [payload]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                amount = current.get("amount")
                if amount is not None and any(key in current for key in ("totalPrice", "price", "fare", "lowestPrice", "calLowestPrice")):
                    return f"${amount}"
                for key, value in current.items():
                    if key in {"totalPrice", "price", "fare", "lowestPrice"} and isinstance(value, dict):
                        nested_amount = value.get("amount") or value.get("total") or value.get("value")
                        if nested_amount is not None:
                            return f"${nested_amount}"
                    if key == "calLowestPrice" and isinstance(value, (str, int, float)):
                        return f"${value}"
                    stack.append(value)
            elif isinstance(current, list):
                stack.extend(current)
        return None

    def _build_notes(self, payload: dict) -> str:
        parts = []
        for label, keys in (
            ("Departure", ["departureTime", "departTime"]),
            ("Arrival", ["arrivalTime", "arriveTime"]),
            ("Stops", ["stops", "numberOfStops"]),
            ("Cabin", ["cabin", "cabinClass"]),
            ("Bundle", ["brandName", "bundleName", "fareClass"]),
        ):
            value = self._pick_value(payload, keys)
            if value:
                parts.append(f"{label}: {value}")
        return "; ".join(parts) or "WestJet fare result"
