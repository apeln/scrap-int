# Fareframe

`Fareframe` is a flight-price monitoring project organized around one scraper per website.
Each supported site gets its own module that knows how to fetch, parse, and normalize offers
into a shared data model.

## Why this structure

- Shared core logic stays in one place.
- Site-specific code is isolated and easier to extend.
- New scrapers can be added without rewriting the CLI or storage layer.

## Project layout

```text
src/fareframe/
  cli.py                 Command line entrypoint
  models.py              Shared request/result models
  core/
    base.py              Base scraper contract
    registry.py          Scraper registration and lookup
  scrapers/
    example_site.py      Example scraper to copy for new sites
tests/
  test_registry.py       Basic project smoke test
```

## Getting started

1. Create a virtual environment.
2. Install the project in editable mode: `pip install -e .`
3. Run the CLI: `fareframe scan example-site --origin SFO --destination JFK --date 2026-05-01`

## Email notifications

Copy `fareframe.settings.toml.example` to `fareframe.settings.toml` and fill in your SMTP settings.

Example:

```toml
[browser]
headless = false
viewport_width = 1440
viewport_height = 1200
page_load_timeout_ms = 120000
initial_page_wait_ms = 5000
short_wait_ms = 500
suggestion_wait_ms = 1500
confirm_wait_ms = 1000
post_search_wait_ms = 30000
browser_executables = [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
]

[sites]
aircanada_url = "https://www.aircanada.com/home/ca/en/aco/flights"
westjet_url = "https://www.westjet.com/en-ca"

[notifications.email]
enabled = true
to = ["alexander.plsk@gmail.com"]
smtp_host = "smtp.gmail.com"
smtp_port = 587
smtp_username = "your-email@gmail.com"
smtp_password = "your-app-password"
from_address = "your-email@gmail.com"
use_tls = true
subject_prefix = "Fareframe"
```

`browser.*` controls browser automation timing and viewport values.
`sites.*` lets you override the target booking URLs without editing code.
`browser.post_search_wait_ms` controls how long the browser stays open after clicking Search before Fareframe collects the loaded results and closes the browser.

Then run the CLI normally, or point to a custom config file with:

`fareframe --settings-file path/to/fareframe.settings.toml scan aircanada --origin YVR --destination YYZ --date 2026-04-05 --return-date 2026-04-12`

## Adding a new website

1. Create a new file in `src/fareframe/scrapers/`.
2. Subclass `BaseScraper`.
3. Register the scraper with `@register_scraper("your-site-name")`.
4. Return normalized `FlightOffer` objects from `search()`.

The included `ExampleSiteScraper` is intentionally simple and acts as a template.
