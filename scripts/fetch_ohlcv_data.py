"""Fetch day-end PSX OHLCV data via yfinance and load it into Neon Postgres.

Standalone counterpart to the `fetch_ohlcv_data` task in dags/psx_pipeline.py,
for use outside Airflow (see .github/workflows/daily_pipeline.yml). Reads the
connection from the NEON_DATABASE_URL env var instead of NEON_HOST/NEON_PASSWORD.

NOTE: yfinance PSX split handling is unreliable — may adjust partially or on the
wrong date. On corporate actions: back up the symbol's rows, inspect where values
change units, adjust only old-unit rows.
"""
import logging
import os
from datetime import datetime, timezone

import psycopg2
import yfinance as yf
from psycopg2.extras import execute_values

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SYMBOLS = ["ISL.KA", "KEL.KA", "LUCK.KA", "NATF.KA", "OGDC.KA", "SYS.KA", "CLOV.KA", "FFC.KA", "SEARL.KA"]


def rows_from_history(sym, df):
    """Convert a yfinance history DataFrame into psx_price_history row tuples."""
    # Use the PSX trading date (Asia/Karachi), not UTC — converting to UTC first
    # rolls the midnight-PKT timestamp back onto the previous calendar day.
    df.index = df.index.tz_convert("Asia/Karachi").normalize()

    return [
        (
            sym.replace(".KA", ""),
            idx.date(),
            round(float(row["Open"]), 4),
            round(float(row["High"]), 4),
            round(float(row["Low"]), 4),
            round(float(row["Close"]), 4),
            int(row["Volume"]),
            round(float(row["Dividends"]), 4),
            round(float(row["Stock Splits"]), 4),
            datetime.now(timezone.utc),
        )
        for idx, row in df.iterrows()
    ]


def upsert_rows(conn, rows):
    """Upsert psx_price_history row tuples produced by rows_from_history()."""
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO public.psx_price_history
                (symbol, price_date, open, high, low, close, volume, dividends, stock_splits, fetched_at)
            VALUES %s
            ON CONFLICT (symbol, price_date) DO NOTHING
            """,
            rows,
        )
    conn.commit()


def main():
    conn = psycopg2.connect(os.environ["NEON_DATABASE_URL"])

    for sym in SYMBOLS:
        log.info(f"[OHLCV] Fetching {sym}...")
        try:
            df = yf.Ticker(sym).history(period="5d")
            if df.empty:
                log.warning(f"[OHLCV] No data for {sym}, skipping")
                continue

            rows = rows_from_history(sym, df)
            upsert_rows(conn, rows)
            log.info(f"[OHLCV] Done {sym}")

        except Exception as e:
            conn.rollback()
            log.error(f"[OHLCV] ERROR for {sym}: {e}")

    conn.close()
    log.info("[OHLCV] fetch_ohlcv_data complete")


if __name__ == "__main__":
    main()
