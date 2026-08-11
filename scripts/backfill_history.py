"""One-off backfill of 1 year of daily PSX OHLCV history via yfinance into Neon Postgres.

Reuses the row-building and upsert logic from fetch_ohlcv_data.py. Reads the
connection from the NEON_DATABASE_URL env var.
"""
import logging
import os

import psycopg2
import yfinance as yf

from fetch_ohlcv_data import rows_from_history, upsert_rows

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SYMBOLS = ["FFC.KA", "SEARL.KA"]


def main():
    conn = psycopg2.connect(os.environ["NEON_DATABASE_URL"])

    for sym in SYMBOLS:
        log.info(f"[BACKFILL] Fetching {sym}...")
        try:
            df = yf.Ticker(sym).history(period="1y")
            if df.empty:
                log.warning(f"[BACKFILL] No data for {sym}, skipping")
                continue

            rows = rows_from_history(sym, df)
            upsert_rows(conn, rows)
            log.info(f"[BACKFILL] Upserted {len(rows)} rows for {sym}")

        except Exception as e:
            conn.rollback()
            log.error(f"[BACKFILL] ERROR for {sym}: {e}")

    conn.close()
    log.info("[BACKFILL] backfill_history complete")


if __name__ == "__main__":
    main()
