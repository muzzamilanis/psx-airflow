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

    seed = seed_dbt()
    dbt = run_dbt()
    dbt_test = test_dbt()

    seed >> dbt >> dbt_test

psx_pipeline()
