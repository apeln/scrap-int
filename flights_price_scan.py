#!/usr/bin/env python3
"""
Quick flight page scanner.

Given a flights webpage URL and route filters (date/source/destination),
this script collects visible price-like values and returns a table.

Notes:
- Many flight websites are dynamic and may block scraping. In those cases,
  use the optional Playwright mode (--use-playwright) to render JS.
- This is intended as a quick generic scraper, not a site-specific parser.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from typing import Iterable

import pandas as pd
import requests
from bs4 import BeautifulSoup

PRICE_RE = re.compile(
    r"(?:USD\s*)?(?:\$|€|£|₹)\s?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?|\d+[.,]\d{2}\s?(?:USD|EUR|GBP|INR)",
    re.IGNORECASE,
)


@dataclass
class Candidate:
    date: str
    source: str
    destination: str
    price: str
    snippet: str


def fetch_html(url: str, use_playwright: bool, timeout: int = 30) -> str:
    if use_playwright:
        # lazy import so normal mode has minimal dependencies
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
            html = page.content()
            browser.close()
            return html

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def row_texts_from_tables(html: str) -> list[str]:
    rows: list[str] = []
    try:
        for df in pd.read_html(html):
            for _, row in df.iterrows():
                values = [str(v) for v in row.tolist() if str(v) != "nan"]
                if values:
                    rows.append(" | ".join(values))
    except ValueError:
        # no HTML tables found
        pass
    return rows


def row_texts_from_blocks(soup: BeautifulSoup) -> Iterable[str]:
    # Generic card/list elements frequently used in flight sites.
    selectors = [
        "article",
        "li",
        "div.flight",
        "div.result",
        "div.card",
        "div[class*='flight']",
        "div[class*='result']",
    ]
    seen = set()
    for sel in selectors:
        for node in soup.select(sel):
            text = " ".join(node.stripped_strings)
            if len(text) < 30:
                continue
            if text in seen:
                continue
            seen.add(text)
            yield text


def matches_route(text: str, date: str, source: str, destination: str) -> bool:
    t = normalize(text)
    return all(part in t for part in [normalize(date), normalize(source), normalize(destination)])


def extract_candidates(html: str, date: str, source: str, destination: str) -> list[Candidate]:
    soup = BeautifulSoup(html, "html.parser")

    blocks = list(row_texts_from_tables(html))
    blocks.extend(row_texts_from_blocks(soup))

    out: list[Candidate] = []
    for block in blocks:
        if not matches_route(block, date, source, destination):
            continue

        prices = PRICE_RE.findall(block)
        for p in prices:
            out.append(
                Candidate(
                    date=date,
                    source=source,
                    destination=destination,
                    price=p.strip(),
                    snippet=block[:240],
                )
            )

    # fallback: if route match is too strict, gather any price-containing lines
    if not out:
        for block in blocks:
            prices = PRICE_RE.findall(block)
            for p in prices:
                out.append(
                    Candidate(
                        date=date,
                        source=source,
                        destination=destination,
                        price=p.strip(),
                        snippet=block[:240],
                    )
                )

    return out


def to_dataframe(candidates: list[Candidate]) -> pd.DataFrame:
    if not candidates:
        return pd.DataFrame(columns=["date", "source", "destination", "price", "snippet"])

    df = pd.DataFrame([c.__dict__ for c in candidates])
    return df.drop_duplicates().reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan a flights webpage and extract prices into a table.")
    parser.add_argument("url", help="Flights search/result webpage URL")
    parser.add_argument("--date", required=True, help="Flight date text as it appears on page, e.g. 2026-04-30")
    parser.add_argument("--source", required=True, help="Source city/airport, e.g. SFO")
    parser.add_argument("--destination", required=True, help="Destination city/airport, e.g. JFK")
    parser.add_argument("--csv", default="", help="Optional path to write CSV output")
    parser.add_argument("--use-playwright", action="store_true", help="Render JavaScript-heavy pages before parsing")

    args = parser.parse_args()

    try:
        html = fetch_html(args.url, use_playwright=args.use_playwright)
    except Exception as exc:
        print(f"Failed to fetch page: {exc}", file=sys.stderr)
        return 1

    df = to_dataframe(extract_candidates(html, args.date, args.source, args.destination))

    if df.empty:
        print("No prices found for the given filters.")
        return 0

    print(df.to_markdown(index=False))

    if args.csv:
        df.to_csv(args.csv, index=False)
        print(f"\nSaved {len(df)} rows to {args.csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
