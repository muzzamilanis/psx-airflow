FROM apache/airflow:2.9.1-python3.11

USER root
RUN apt-get update && apt-get install -y git && apt-get clean

COPY requirements.txt /requirements.txt
COPY dags/ /opt/airflow/dags/
COPY include/ /opt/airflow/include/

RUN mkdir -p /opt/airflow/include/psx_analytics /opt/airflow/logs && \
    chmod -R 777 /opt/airflow/include /opt/airflow/logs && \
    chown -R airflow:root /opt/airflow/include /opt/airflow/logs

USER airflow

RUN pip install --no-cache-dir -r /requirements.txt

ENTRYPOINT ["/bin/bash", "-c"]
CMD ["printf '%s' \"$DBT_PROFILES_YML\" > /opt/airflow/include/psx_analytics/profiles.yml && \
airflow db init && \
airflow users create --username admin --password admin --firstname Admin --lastname User --role Admin --email admin@example.com 2>/dev/null || true && \
sleep 5 && \
airflow scheduler & \
sleep 10 && \
airflow webserver --port 8080"]
