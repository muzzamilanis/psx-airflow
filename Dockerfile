FROM apache/airflow:2.9.1-python3.11

USER root
RUN apt-get update && apt-get install -y git && apt-get clean

COPY requirements.txt /requirements.txt
COPY dags/ /opt/airflow/dags/
COPY include/ /opt/airflow/include/

RUN mkdir -p /opt/airflow/include/psx_analytics && \
    chmod -R 777 /opt/airflow/include && \
    chown -R airflow:root /opt/airflow/include

USER airflow

RUN pip install --no-cache-dir -r /requirements.txt

ENTRYPOINT ["/bin/bash", "-c"]
CMD ["printf '%s' \"$DBT_PROFILES_YML\" > /opt/airflow/include/psx_analytics/profiles.yml && \
airflow db migrate && \
airflow users create --username admin --password admin --firstname Admin --lastname User --role Admin --email admin@example.com 2>/dev/null || true && \
airflow scheduler & \
airflow webserver --port 8080"]
