from airflow.decorators import dag, task
from pendulum import datetime
from datetime import timedelta
import logging

log = logging.getLogger(__name__)
DBT_PROJECT_DIR = "/usr/local/airflow/include/psx_analytics"

def on_failure_callback(context):
    log.error(f"Task {context['task_instance'].task_id} failed on DAG {context['dag'].dag_id}")

@dag(
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["psx"],
    default_args={
        "retries": 3,
        "retry_delay": timedelta(minutes=5),
        "on_failure_callback": on_failure_callback,
    },
)
def psx_pipeline():

    @task
    def seed_dbt():
        import subprocess
        result = subprocess.run(
            ["dbt", "seed",
             "--project-dir", DBT_PROJECT_DIR,
             "--profiles-dir", DBT_PROJECT_DIR],
            capture_output=True, text=True
        )
        log.info("[DBT SEED] stdout: %s", result.stdout)
        if result.returncode != 0:
            raise RuntimeError(f"dbt seed failed: {result.stderr}")
        log.info("[DBT SEED] Completed successfully")

    @task
    def run_dbt():
        import subprocess
        result = subprocess.run(
            ["dbt", "run",
             "--project-dir", DBT_PROJECT_DIR,
             "--profiles-dir", DBT_PROJECT_DIR],
            capture_output=True, text=True
        )
        log.info("[DBT RUN] stdout: %s", result.stdout)
        if result.returncode != 0:
            raise RuntimeError(f"dbt run failed: {result.stderr}")
        log.info("[DBT RUN] Completed successfully")

    @task
    def test_dbt():
        import subprocess
        result = subprocess.run(
            ["dbt", "test",
             "--project-dir", DBT_PROJECT_DIR,
             "--profiles-dir", DBT_PROJECT_DIR],
            capture_output=True, text=True
        )
        log.info("[DBT TEST] stdout: %s", result.stdout)
        if result.returncode != 0:
            raise RuntimeError(f"dbt test failed: {result.stderr}")
        log.info("[DBT TEST] Completed successfully")

    @task
    def sync_neon_to_snowflake():
        import psycopg2
        import snowflake.connector
        import os

        neon_conn = psycopg2.connect(
            host=os.environ["NEON_HOST"],
            dbname="PsxDataLake",
            user="neondb_owner",
            password=os.environ["NEON_PASSWORD"],
            port=5432,
            sslmode="require"
        )
        sf_conn = snowflake.connector.connect(
            account="gcubopn-la25479",
            user=os.environ["SNOWFLAKE_USER"],
            password=os.environ["SNOWFLAKE_PASSWORD"],
            database="PSX_DATA_LAKE",
            schema="BRONZE",
            warehouse="COMPUTE_WH"
        )

        neon_cur = neon_conn.cursor()
        sf_cur = sf_conn.cursor()

        sf_cur.execute('SELECT MAX(id) FROM PSX_DATA_LAKE.BRONZE."PsxAllShr"')
        last_id = sf_cur.fetchone()[0] or 0
        log.info(f"[SYNC] Last synced id: {last_id}")

        neon_cur.execute('SELECT * FROM public."PsxAllShr" WHERE id > %s ORDER BY id', (last_id,))
        rows = neon_cur.fetchall()
        log.info(f"[SYNC] New rows to sync: {len(rows)}")

        if rows:
            sf_cur.executemany(
                'INSERT INTO PSX_DATA_LAKE.BRONZE."PsxAllShr" VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                rows
            )
            sf_conn.commit()
            log.info(f"[SYNC] Synced {len(rows)} rows to Snowflake")
        else:
            log.info("[SYNC] No new rows to sync")

        neon_cur.close()
        neon_conn.close()
        sf_cur.close()
        sf_conn.close()

    @task
    def seed_dbt_snowflake():
        import subprocess
        result = subprocess.run(
            ["dbt", "seed",
             "--project-dir", DBT_PROJECT_DIR,
             "--profiles-dir", DBT_PROJECT_DIR,
             "--target", "snowflake"],
            capture_output=True, text=True
        )
        log.info("[DBT SEED SNOWFLAKE] stdout: %s", result.stdout)
        if result.returncode != 0:
            raise RuntimeError(f"dbt seed snowflake failed: {result.stderr}")
        log.info("[DBT SEED SNOWFLAKE] Completed successfully")

    @task
    def run_dbt_snowflake():
        import subprocess
        result = subprocess.run(
            ["dbt", "run",
             "--project-dir", DBT_PROJECT_DIR,
             "--profiles-dir", DBT_PROJECT_DIR,
             "--target", "snowflake",
             "--vars", '{"source_database": "PSX_DATA_LAKE", "source_schema": "BRONZE"}'],
            capture_output=True, text=True
        )
        log.info("[DBT SNOWFLAKE] stdout: %s", result.stdout)
        if result.returncode != 0:
            raise RuntimeError(f"dbt snowflake run failed: {result.stderr}")
        log.info("[DBT SNOWFLAKE] Completed successfully")


    @task
    def fetch_ohlcv_data():
        import os
        import yfinance as yf
        import psycopg2
        from psycopg2.extras import execute_values
        from datetime import datetime, timezone

        SYMBOLS = ['ISL.KA', 'KEL.KA', 'LUCK.KA', 'NATF.KA', 'OGDC.KA', 'SYS.KA', 'CLOV.KA']

        conn = psycopg2.connect(
            host=os.environ["NEON_HOST"],
            dbname="PsxDataLake",
            user="neondb_owner",
            password=os.environ["NEON_PASSWORD"],
            port=5432,
            sslmode="require"
        )

        for sym in SYMBOLS:
            log.info(f"[OHLCV] Fetching {sym}...")
            try:
                df = yf.Ticker(sym).history(period='5d')
                if df.empty:
                    log.warning(f"[OHLCV] No data for {sym}, skipping")
                    continue

                df.index = df.index.tz_convert('UTC').normalize()

                rows = [
                    (
                        sym.replace('.KA', ''),
                        idx.date(),
                        round(float(row['Open']), 4),
                        round(float(row['High']), 4),
                        round(float(row['Low']), 4),
                        round(float(row['Close']), 4),
                        int(row['Volume']),
                        round(float(row['Dividends']), 4),
                        round(float(row['Stock Splits']), 4),
                        datetime.now(timezone.utc)
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
                        rows
                    )
                conn.commit()
                log.info(f"[OHLCV] Done {sym}")

            except Exception as e:
                conn.rollback()
                log.error(f"[OHLCV] ERROR for {sym}: {e}")

        conn.close()
        log.info("[OHLCV] fetch_ohlcv_data complete")

    ohlcv     = fetch_ohlcv_data()
    seed      = seed_dbt()
    dbt       = run_dbt()
    test      = test_dbt()
    # sync      = sync_neon_to_snowflake()
    # sf_seed   = seed_dbt_snowflake()
    # sf_dbt    = run_dbt_snowflake()

    ohlcv >> seed >> dbt >> test

psx_pipeline()
