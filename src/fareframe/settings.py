from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(slots=True)
class EmailSettings:
    enabled: bool = False
    to: tuple[str, ...] = ()
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    from_address: str = ""
    use_tls: bool = True
    subject_prefix: str = "Fareframe"


@dataclass(slots=True)
class BrowserSettings:
    headless: bool = False
    viewport_width: int = 1440
    viewport_height: int = 1200
    page_load_timeout_ms: int = 120000
    initial_page_wait_ms: int = 5000
    short_wait_ms: int = 500
    suggestion_wait_ms: int = 1500
    confirm_wait_ms: int = 1000
    post_search_wait_ms: int = 30000
    results_settle_wait_ms: int = 5000
    browser_executables: tuple[str, ...] = (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    )


@dataclass(slots=True)
class SiteSettings:
    aircanada_url: str = "https://www.aircanada.com/home/ca/en/aco/flights"
    westjet_url: str = "https://www.westjet.com/en-ca"


@dataclass(slots=True)
class Settings:
    email: EmailSettings
    browser: BrowserSettings
    sites: SiteSettings


_CURRENT_SETTINGS = Settings(
    email=EmailSettings(),
    browser=BrowserSettings(),
    sites=SiteSettings(),
)


def load_settings(config_path: str | None = None) -> Settings:
    path = Path(config_path) if config_path else Path.cwd() / "fareframe.settings.toml"
    if not path.exists():
        return Settings(
            email=EmailSettings(),
            browser=BrowserSettings(),
            sites=SiteSettings(),
        )

    with path.open("rb") as handle:
        data = tomllib.load(handle)

    email_data = data.get("notifications", {}).get("email", {})
    browser_data = data.get("browser", {})
    site_data = data.get("sites", {})
    return Settings(
        email=EmailSettings(
            enabled=bool(email_data.get("enabled", False)),
            to=tuple(email_data.get("to", [])),
            smtp_host=str(email_data.get("smtp_host", "")),
            smtp_port=int(email_data.get("smtp_port", 587)),
            smtp_username=str(email_data.get("smtp_username", "")),
            smtp_password=str(email_data.get("smtp_password", "")),
            from_address=str(email_data.get("from_address", "")),
            use_tls=bool(email_data.get("use_tls", True)),
            subject_prefix=str(email_data.get("subject_prefix", "Fareframe")),
        ),
        browser=BrowserSettings(
            headless=bool(browser_data.get("headless", False)),
            viewport_width=int(browser_data.get("viewport_width", 1440)),
            viewport_height=int(browser_data.get("viewport_height", 1200)),
            page_load_timeout_ms=int(browser_data.get("page_load_timeout_ms", 120000)),
            initial_page_wait_ms=int(browser_data.get("initial_page_wait_ms", 5000)),
            short_wait_ms=int(browser_data.get("short_wait_ms", 500)),
            suggestion_wait_ms=int(browser_data.get("suggestion_wait_ms", 1500)),
            confirm_wait_ms=int(browser_data.get("confirm_wait_ms", 1000)),
            post_search_wait_ms=int(browser_data.get("post_search_wait_ms", 30000)),
            results_settle_wait_ms=int(browser_data.get("results_settle_wait_ms", 5000)),
            browser_executables=tuple(
                browser_data.get(
                    "browser_executables",
                    [
                        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                    ],
                )
            ),
        ),
        sites=SiteSettings(
            aircanada_url=str(
                site_data.get("aircanada_url", "https://www.aircanada.com/home/ca/en/aco/flights")
            ),
            westjet_url=str(site_data.get("westjet_url", "https://www.westjet.com/en-ca")),
        ),
    )


def configure_settings(settings: Settings) -> None:
    global _CURRENT_SETTINGS
    _CURRENT_SETTINGS = settings


def get_settings() -> Settings:
    return _CURRENT_SETTINGS
