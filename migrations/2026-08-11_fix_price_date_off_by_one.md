# Fix: psx_price_history.price_date stored one day early

## Bug

`rows_from_history()` (scripts/fetch_ohlcv_data.py) and the equivalent inline
code in the `fetch_ohlcv_data` Airflow task (dags/psx_pipeline.py) converted
yfinance's PSX timestamps to UTC before taking the calendar date:

```python
df.index = df.index.tz_convert("UTC").normalize()
```

yfinance already returns PSX bars indexed at midnight `Asia/Karachi` (PKT,
UTC+5). Converting to UTC first rolls that midnight timestamp back onto the
previous calendar day (e.g. `2026-08-10 00:00:00+05:00` -> `2026-08-09
19:00:00 UTC` -> normalized to `2026-08-09`), so every row was stored one
trading day early.

Proof: `SELECT EXTRACT(DOW FROM price_date), COUNT(*) FROM psx_price_history
GROUP BY 1` returned ~1,975 rows on Sunday (DOW 0) and zero on Friday (DOW 5)
— PSX trades Mon-Fri, so the whole table was shifted back one day.

## Data migration (run 2026-08-11 against Neon)

```sql
-- 1. Backup
CREATE TABLE price_history_backup AS SELECT * FROM psx_price_history;

-- 2. Shift all rows +1 day. Done in two steps because a single
--    `price_date + INTERVAL '1 day'` UPDATE can collide mid-statement with
--    the UNIQUE (symbol, price_date) constraint. An offset of 1000/999 days
--    (as commonly suggested) is NOT safe for this table — some symbols
--    (CLOV, ISL, KEL, LUCK, NATF, OGDC, SYS) have ~1,890 days of history, so
--    two same-symbol rows can legitimately be exactly 1000 days apart and
--    collide. Used 5000/4999 instead, safely larger than the max per-symbol
--    date span.
UPDATE psx_price_history SET price_date = price_date + INTERVAL '5000 days';
UPDATE psx_price_history SET price_date = price_date - INTERVAL '4999 days';
```

Verified post-migration by joining every row back to `price_history_backup`
on `(symbol, backup.price_date + 1 day)`: 9,830 rows before and after, zero
unmatched/extra current rows, zero missing rows, zero OHLCV value mismatches.
`price_history_backup` is left in place as a rollback snapshot.

## Code fix

Changed `tz_convert("UTC")` to `tz_convert("Asia/Karachi")` before
`.normalize()` in:
- `scripts/fetch_ohlcv_data.py` (`rows_from_history()`) — also used by
  `scripts/backfill_history.py`, which imports this function.
- `dags/psx_pipeline.py` (`fetch_ohlcv_data` task, inline copy of the same
  logic).

This must ship in the same commit as the data migration: the migration
assumes the *next* fetch runs with corrected code. Deploying the shifted
table without the code fix means the next scheduled fetch inserts a new row
one day early again, on top of already-corrected history.
