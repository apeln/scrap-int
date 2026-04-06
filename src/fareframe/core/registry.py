from __future__ import annotations

from collections.abc import Callable

from fareframe.core.base import BaseScraper

ScraperFactory = Callable[[], BaseScraper]

_SCRAPERS: dict[str, ScraperFactory] = {}


def register_scraper(site_name: str) -> Callable[[type[BaseScraper]], type[BaseScraper]]:
    def decorator(scraper_cls: type[BaseScraper]) -> type[BaseScraper]:
        _SCRAPERS[site_name] = scraper_cls
        scraper_cls.site_name = site_name
        return scraper_cls

    return decorator


def build_scraper(site_name: str) -> BaseScraper:
    try:
        scraper_cls = _SCRAPERS[site_name]
    except KeyError as exc:
        known_sites = ", ".join(sorted(_SCRAPERS)) or "none"
        raise ValueError(f"Unknown site '{site_name}'. Known sites: {known_sites}") from exc

    return scraper_cls()


def available_sites() -> list[str]:
    return sorted(_SCRAPERS)
