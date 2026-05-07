FROM apache/airflow:3.0.0-python3.11

USER root
RUN apt-get update && apt-get install -y git && apt-get clean

COPY requirements.txt /requirements.txt
COPY debug_db.py /debug_db.py
COPY dags/ /opt/airflow/dags/
COPY include/ /opt/airflow/include/

RUN mkdir -p /opt/airflow/include/psx_analytics /opt/airflow/logs && \
    chmod -R 777 /opt/airflow/include /opt/airflow/logs && \
    chown -R airflow:root /opt/airflow/include /opt/airflow/logs

USER airflow

RUN pip install --no-cache-dir -r /requirements.txt

ENTRYPOINT ["/bin/bash", "-c"]
CMD ["python /debug_db.py"]
