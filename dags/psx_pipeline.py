from airflow.sdk import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from pendulum import datetime
import logging

log = logging.getLogger(__name__)

DBT_PROJECT_DIR = "/usr/local/airflow/include/psx_analytics"

@dag(
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["psx"],
)
def psx_pipeline():

    @task
    def scrape_psx():
        from psycopg2.extras import execute_values

        mock_rows = [
            ("ENGRO", "Engro Corporation", "285.50", "287.00", "1.50", "0.53", "2.41", "6.89", "15234567", "1250.5", "342000.0"),
            ("LUCK", "Lucky Cement", "920.00", "915.00", "-5.00", "-0.54", "1.89", "17.23", "8923412", "890.2", "1250000.0"),
            ("HBL", "Habib Bank Limited", "145.00", "146.50", "1.50", "1.03", "3.12", "4.51", "22341234", "2100.8", "890000.0"),
            ("PSO", "Pakistan State Oil", "310.00", "308.00", "-2.00", "-0.65", "1.95", "6.03", "5678901", "780.3", "560000.0"),
            ("TRG", "TRG Pakistan", "98.50", "99.00", "0.50", "0.51", "0.87", "0.86", "3456789", "420.1", "125000.0"),
        ]

        columns = ["symbol", "name", "ldcp", "current", "change", "change_1",
                   "idx_wtg", "idx_point", "volume", "shares_m", "market_cap_m"]

        TABLE_NAME = "PsxAllShr"
        hook = PostgresHook(postgres_conn_id="neon_postgres")
        conn = hook.get_conn()
        conn.autocommit = False

        with conn.cursor() as cur:
            col_list = ", ".join(f'"{c}"' for c in columns)
            execute_values(
                cur,
                f'INSERT INTO "{TABLE_NAME}" ({col_list}) VALUES %s',
                mock_rows
            )

        conn.commit()
        conn.close()
        log.info("[SCRAPE] Inserted %d mock rows", len(mock_rows))

    @task
    def seed_dbt():
        import subprocess
        result = subprocess.run(
            ["dbt", "seed",
             "--project-dir", DBT_PROJECT_DIR,
             "--profiles-dir", DBT_PROJECT_DIR],
            capture_output=True,
            text=True
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
            capture_output=True,
            text=True
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
            capture_output=True,
            text=True
        )
        log.info("[DBT TEST] stdout: %s", result.stdout)
        if result.returncode != 0:
            raise RuntimeError(f"dbt test failed: {result.stderr}")
        log.info("[DBT TEST] Completed successfully")

    scrape = scrape_psx()
    seed = seed_dbt()
    dbt = run_dbt()
    dbt_test = test_dbt()

    scrape >> seed >> dbt >> dbt_test

psx_pipeline()