import psycopg2
import snowflake.connector
import os

# Neon connection
neon_conn = psycopg2.connect(
    host=os.environ["NEON_HOST"],
    dbname="PsxDataLake",
    user="neondb_owner",
    password=os.environ["NEON_PASSWORD"],
    port=5432,
    sslmode="require"
)

# Snowflake connection
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

# Create table in Snowflake if not exists
sf_cur.execute("""
    CREATE TABLE IF NOT EXISTS PSX_DATA_LAKE.BRONZE."PsxAllShr" (
        id            INTEGER,
        fetched_at    TIMESTAMP,
        symbol        VARCHAR,
        name          VARCHAR,
        ldcp          VARCHAR,
        "current"     VARCHAR,
        change        VARCHAR,
        change_1      VARCHAR,
        idx_wtg       VARCHAR,
        idx_point     VARCHAR,
        volume        VARCHAR,
        shares_m      VARCHAR,
        market_cap_m  VARCHAR
    )
""")

# Get last synced id from Snowflake
sf_cur.execute('SELECT MAX(id) FROM PSX_DATA_LAKE.BRONZE."PsxAllShr"')
last_id = sf_cur.fetchone()[0] or 0
print(f"Last synced id: {last_id}")

# Fetch new rows from Neon
neon_cur.execute('SELECT * FROM public."PsxAllShr" WHERE id > %s ORDER BY id', (last_id,))
rows = neon_cur.fetchall()
print(f"New rows to sync: {len(rows)}")

if rows:
    sf_cur.executemany(
        'INSERT INTO PSX_DATA_LAKE.BRONZE."PsxAllShr" VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
        rows
    )
    sf_conn.commit()
    print(f"Synced {len(rows)} rows to Snowflake")
else:
    print("No new rows to sync")

neon_cur.close()
neon_conn.close()
sf_cur.close()
sf_conn.close()
