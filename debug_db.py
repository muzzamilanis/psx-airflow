import traceback
import os

os.environ.setdefault("AIRFLOW__DATABASE__SQL_ALCHEMY_CONN", os.getenv("AIRFLOW__DATABASE__SQL_ALCHEMY_CONN", ""))

try:
    from airflow.utils.db import initdb
    initdb()
    print("INITDB SUCCESS")
except Exception as e:
    traceback.print_exc()
    print("INITDB FAILED:", e)
