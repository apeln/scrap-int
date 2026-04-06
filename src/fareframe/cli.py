from __future__ import annotations

import argparse

from fareframe.notifications import send_email_report
from fareframe.core.registry import available_sites, build_scraper
from fareframe.models import FlightOffer, SearchRequest
from fareframe.settings import configure_settings, load_settings
import fareframe.scrapers  # noqa: F401


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a flight scraper for a specific website.")
    parser.add_argument(
        "--settings-file",
        help="Path to a fareframe.settings.toml file",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Run a scraper for a given site")
    scan_parser.add_argument("site", help="Registered site key, such as example-site")
    scan_parser.add_argument("--origin", required=True, help="Origin airport or city code")
    scan_parser.add_argument("--destination", required=True, help="Destination airport or city code")
    scan_parser.add_argument("--date", required=True, help="Travel date in YYYY-MM-DD format")
    scan_parser.add_argument("--return-date", help="Return date in YYYY-MM-DD format")

    subparsers.add_parser("sites", help="List registered sites")
    return parser


def _format_table(offers: list[FlightOffer]) -> str:
    columns = [
        ("site", "Site"),
        ("origin", "Origin"),
        ("destination", "Destination"),
        ("date", "Date"),
        ("price_text", "Status"),
        ("currency", "Currency"),
        ("deep_link", "URL"),
        ("notes", "Notes"),
    ]
    rows = []
    for offer in offers:
        rows.append([str(getattr(offer, field) or "") for field, _ in columns])

    widths = []
    for index, (_, header) in enumerate(columns):
        cell_width = max((len(row[index]) for row in rows), default=0)
        widths.append(max(len(header), cell_width))

    header_line = " | ".join(
        header.ljust(widths[index]) for index, (_, header) in enumerate(columns)
    )
    divider_line = "-+-".join("-" * width for width in widths)
    data_lines = [
        " | ".join(row[index].ljust(widths[index]) for index in range(len(columns)))
        for row in rows
    ]
    return "\n".join([header_line, divider_line, *data_lines])


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    settings = load_settings(args.settings_file)
    configure_settings(settings)

    if args.command == "sites":
        for site in available_sites():
            print(site)
        return 0

    request = SearchRequest(
        site=args.site,
        origin=args.origin,
        destination=args.destination,
        date=args.date,
        return_date=args.return_date,
    )
    scraper = build_scraper(args.site)
    offers = scraper.search(request)
    report = _format_table(offers)
    print(report)
    send_email_report(
        email_settings=settings.email,
        site=args.site,
        report_body=report,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
