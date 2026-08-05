"""Fetch day-end PSX OHLCV data via yfinance and load it into Neon Postgres.

Standalone counterpart to the `fetch_ohlcv_data` task in dags/psx_pipeline.py,
for use outside Airflow (see .github/workflows/daily_pipeline.yml). Reads the
connection from the NEON_DATABASE_URL env var instead of NEON_HOST/NEON_PASSWORD.
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


def main():
    conn = psycopg2.connect(os.environ["NEON_DATABASE_URL"])

    for sym in SYMBOLS:
        log.info(f"[OHLCV] Fetching {sym}...")
        try:
            df = yf.Ticker(sym).history(period="5d")
            if df.empty:
                log.warning(f"[OHLCV] No data for {sym}, skipping")
                continue

            df.index = df.index.tz_convert("UTC").normalize()

            rows = [
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
            log.info(f"[OHLCV] Done {sym}")

        except Exception as e:
            conn.rollback()
            log.error(f"[OHLCV] ERROR for {sym}: {e}")

    conn.close()
    log.info("[OHLCV] fetch_ohlcv_data complete")


if __name__ == "__main__":
    main()
