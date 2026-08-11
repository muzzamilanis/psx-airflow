"""Deterministic news ingestion for the PSX pipeline. No LLM involvement.

Pulls from three sources into raw_news, deduped on url via ON CONFLICT DO NOTHING:
  - Business Recorder RSS (business + markets feeds)
  - Dawn Business RSS
  - PSX company announcements (dps.psx.com.pk) for the tracked symbols

RSS items store title + summary/description as body — full article pages are
NOT fetched in v1. Each source runs in its own try/except so one dead source
doesn't kill the run; counts are logged per source.

PSX announcement rows also record which symbol they were queried for; RSS
rows leave symbol null.

Reads the connection from the NEON_DATABASE_URL env var, matching
fetch_ohlcv_data.py.
"""
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import psycopg2
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}
REQUEST_TIMEOUT = 20

RSS_FEEDS = {
    "business_recorder": [
        "https://www.brecorder.com/feeds/business",
        "https://www.brecorder.com/feeds/markets",
    ],
    "dawn_business": [
        "https://www.dawn.com/feeds/business",
    ],
}

PSX_SYMBOLS = ["CLOV", "FFC", "ISL", "KEL", "LUCK", "OGDC", "SEARL", "SYS"]
PSX_BASE_URL = "https://dps.psx.com.pk"
PSX_ANNOUNCEMENTS_URL = f"{PSX_BASE_URL}/announcements"
PSX_TZ = ZoneInfo("Asia/Karachi")
PSX_REQUEST_DELAY_SECONDS = 1.5

# PSX renders status badges (e.g. REVOKED, REVISED) as extra table-cell markup with
# no separator from the title text, so BeautifulSoup's get_text() glues them onto
# the title, e.g. "Board Meeting Other Than Financial ResultsREVOKED". Split them
# back out into a readable " — STATUS" suffix.
STATUS_SUFFIX_RE = re.compile(r"(REVOKED|REVISED)+$")


def split_status_suffix(title):
    """Separate a glued-on trailing status badge (REVOKED/REVISED) from a title."""
    if not title:
        return title

    match = STATUS_SUFFIX_RE.search(title)
    if not match:
        return title

    prefix = title[: match.start()]
    if not prefix or prefix[-1].isspace():
        return title

    statuses = re.findall(r"REVOKED|REVISED", match.group(0))
    return f"{prefix} — {', '.join(statuses)}"


def insert_row(conn, source, url, title, body, published_at, symbol=None):
    """Insert one raw_news row. Returns True if a new row was inserted."""
    if not url:
        log.warning(f"[{source}] Skipping item with no url: {title!r}")
        return False

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.raw_news (url, source, title, body, published_at, symbol)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO NOTHING
            RETURNING id
            """,
            (url, source, title, body, published_at, symbol),
        )
        inserted = cur.fetchone() is not None
    conn.commit()
    return inserted


def parse_rss_feed(xml_text):
    """Yield (title, link, description, pub_date) tuples from an RSS XML document."""
    root = ET.fromstring(xml_text)
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description_raw = item.findtext("description") or ""
        description = BeautifulSoup(description_raw, "html.parser").get_text().strip()
        pub_date_raw = item.findtext("pubDate")

        pub_date = None
        if pub_date_raw:
            try:
                pub_date = parsedate_to_datetime(pub_date_raw)
            except (TypeError, ValueError):
                log.warning(f"Could not parse pubDate {pub_date_raw!r}")

        yield title, link, description, pub_date


def fetch_rss_source(conn, source_name, feed_urls):
    """Fetch one or more RSS feeds for a source and insert items. Returns inserted count."""
    inserted = 0
    for feed_url in feed_urls:
        resp = requests.get(feed_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()

        for title, link, description, pub_date in parse_rss_feed(resp.content):
            if insert_row(conn, source_name, link, title, description, pub_date):
                inserted += 1

    return inserted


def parse_psx_announcements(html_text, symbol):
    """Yield (title, url, published_at) tuples parsed from the PSX announcements HTML fragment."""
    soup = BeautifulSoup(html_text, "html.parser")
    table = soup.find("table", id="announcementsTable")
    if table is None:
        return

    body = table.find("tbody")
    rows = body.find_all("tr") if body else []

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 6:
            continue

        date_text = cells[0].get_text(strip=True)
        time_text = cells[1].get_text(strip=True)
        title = split_status_suffix(cells[4].get_text(strip=True))

        published_at = None
        try:
            naive = datetime.strptime(f"{date_text} {time_text}", "%b %d, %Y %I:%M %p")
            published_at = naive.replace(tzinfo=PSX_TZ)
        except ValueError:
            log.warning(f"[psx_announcements] Could not parse date {date_text!r} {time_text!r}")

        actions_cell = cells[5]
        doc_link = actions_cell.find("a", href=lambda h: h and h.startswith("/download/document"))
        if doc_link is None:
            doc_link = actions_cell.find("a", href=lambda h: h and h.startswith("/download/attachment"))

        if doc_link is not None:
            url = urljoin(PSX_BASE_URL, doc_link["href"])
        else:
            image_link = actions_cell.find("a", attrs={"data-images": True})
            url = urljoin(PSX_BASE_URL, f"/download/image/{image_link['data-images']}") if image_link else None

        yield title, url, published_at


def fetch_psx_announcements_source(conn):
    """Fetch PSX company announcements for the tracked symbols. Returns inserted count."""
    inserted = 0
    for symbol in PSX_SYMBOLS:
        try:
            resp = requests.post(
                PSX_ANNOUNCEMENTS_URL,
                headers={**HEADERS, "X-Requested-With": "XMLHttpRequest", "Referer": f"{PSX_BASE_URL}/announcements/companies"},
                data={
                    "type": "C",
                    "symbol": symbol,
                    "query": "",
                    "count": 20,
                    "offset": 0,
                    "date_from": "",
                    "date_to": "",
                    "page": "annc",
                },
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()

            symbol_inserted = 0
            for title, url, published_at in parse_psx_announcements(resp.text, symbol):
                if insert_row(conn, "psx_announcements", url, title, None, published_at, symbol=symbol):
                    symbol_inserted += 1

            inserted += symbol_inserted
            log.info(f"[psx_announcements] {symbol}: inserted {symbol_inserted}")

        except Exception as e:
            log.error(f"[psx_announcements] ERROR for {symbol}: {e}")

        time.sleep(PSX_REQUEST_DELAY_SECONDS)

    return inserted


def main():
    conn = psycopg2.connect(os.environ["NEON_DATABASE_URL"])

    for source_name, feed_urls in RSS_FEEDS.items():
        try:
            count = fetch_rss_source(conn, source_name, feed_urls)
            log.info(f"[{source_name}] inserted {count} new rows")
        except Exception as e:
            conn.rollback()
            log.error(f"[{source_name}] ERROR: {e}")

    try:
        count = fetch_psx_announcements_source(conn)
        log.info(f"[psx_announcements] inserted {count} new rows total")
    except Exception as e:
        conn.rollback()
        log.error(f"[psx_announcements] ERROR: {e}")

    conn.close()
    log.info("[NEWS] fetch_news complete")


if __name__ == "__main__":
    main()
