# PSX Data Engineering Pipeline — Airflow Edition

An end-to-end data engineering project that ingests daily Pakistan Stock Exchange (PSX) market data, orchestrates transformations through a Medallion architecture using dbt, and serves analytics-ready datasets for market analysis.

This is the Airflow-orchestrated evolution of the [original PSX pipeline](https://github.com/muzzamilanis/PSX-Financial-Agent), replacing Windows Task Scheduler with Apache Airflow for production-grade scheduling, retries, and observability.

## Architecture

```
PSX Website → Python Scraper → PostgreSQL Bronze Layer (PsxAllShr)
                                            ↓
                                 dbt Staging Model (Silver)
                                            ↓
                          ┌─────────────────┴─────────────────┐
                          ↓                                   ↓
               mart_top_movers (Gold)          mart_sector_summary (Gold)
```

## Pipeline DAG

Four tasks run sequentially on a daily schedule:

```
scrape_psx → seed_dbt → run_dbt → test_dbt
```

| Task | Description |
|---|---|
| `scrape_psx` | Scrapes PSX market data and loads into PostgreSQL bronze layer |
| `seed_dbt` | Loads sector mapping reference data via dbt seed |
| `run_dbt` | Runs staging and mart transformation models |
| `test_dbt` | Executes dbt data quality tests |

## Tech Stack

| Layer | Technology |
|---|---|
| Orchestration | Apache Airflow 3.x (Astronomer Runtime) |
| Ingestion | Python, psycopg2 |
| Storage | PostgreSQL (Neon) |
| Transformation | dbt-core, dbt-postgres |
| Data Quality | dbt tests (not_null, unique) |
| Alerting | Airflow failure callbacks with retries |
| Version Control | Git, GitHub |

## Project Structure

```
psx-airflow/
├── dags/
│   └── psx_pipeline.py          # Main Airflow DAG
├── include/
│   └── psx_analytics/           # dbt project
│       ├── models/
│       │   ├── staging/
│       │   │   ├── stg_psx_daily_snapshot.sql
│       │   │   ├── stg_psx_daily_snapshot.yml
│       │   │   └── sources.yml
│       │   └── marts/
│       │       ├── mart_top_movers.sql
│       │       └── mart_sector_summary.sql
│       └── seeds/
│           └── psx_sector_mapping.csv
├── Dockerfile
├── requirements.txt
└── .env
```

## Data Models

### Bronze Layer — `PsxAllShr`
Raw daily snapshot ingested directly from PSX. All fields stored as-is, completely untouched. Serves as the immutable source of truth.

### Silver Layer — `stg_psx_daily_snapshot`
Cleaned and typed view built on top of raw data. Strips commas and percentage signs, casts all numeric fields to correct types, and nullifies empty strings.

### Gold Layer — `mart_top_movers`
All PSX-listed stocks ranked by daily change percentage. Rebuilt as a table on every pipeline run.

### Gold Layer — `mart_sector_summary`
Sector-level aggregations per day — total market cap, total volume, average change percentage, and average price grouped by sector.

## Reliability

- **Retries:** Each task retries 3 times with a 5-minute delay before failing
- **Failure callbacks:** Logs task and DAG name on every failure for observability
- **dbt tests:** Data quality checks run automatically after every transformation

## Setup

### Prerequisites
- Docker Desktop
- [Astro CLI](https://docs.astronomer.io/astro/cli/install-cli)
- PostgreSQL instance (Neon free tier works)

### Installation

```bash
git clone https://github.com/muzzamilanis/psx-airflow
cd psx-airflow
```

Create a `.env` file with your Neon credentials:

```env
NEON_HOST=your-neon-host
NEON_USER=your-user
NEON_PASSWORD=your-password
NEON_DB=PsxDataLake
```

Configure `include/psx_analytics/profiles.yml`:

```yaml
psx_analytics:
  target: dev
  outputs:
    dev:
      type: postgres
      host: your-neon-host
      port: 5432
      user: your-user
      password: your-password
      dbname: PsxDataLake
      schema: public
      sslmode: require
      connect_timeout: 30
```

### Run

```bash
astro dev start
```

Open [http://localhost:8080](http://localhost:8080) with `admin` / `admin`.

Add a connection under **Admin → Connections**:
- **Connection Id:** `neon_postgres`
- **Connection Type:** `Postgres`
- **Host / Schema / Login / Password / Port:** your Neon credentials

Trigger the `psx_pipeline` DAG.

## Sample Output

**Top movers — 2026-04-28:**

| Symbol | Name | Price (PKR) | Change % | Volume |
|---|---|---|---|---|
| TRSM | Trust Modaraba | 17.24 | +10.02% | 2,082,863 |
| MSCL | Metropolitan Steel | 26.25 | +10.02% | 2,021,553 |
| FCEPL | Frieslandcampina Engro | 85.87 | +10.01% | 1,842,353 |

**Sector summary — 2026-04-28:**

| Sector | Avg Change % | Total Market Cap (M) |
|---|---|---|
| Oil & Gas Exploration | -0.75% | 2,759,643 |
| Fertilizer | -0.95% | 1,011,184 |
| Cement | -1.32% | 732,124 |

## Roadmap
- [ ] Replace mock scraper with live PSX data feed
- [ ] Add Slack alerting on pipeline failure
- [ ] Build analytics dashboard (Metabase / Superset)
- [ ] Add historical trend marts (30-day moving average, RSI)
- [ ] Deploy to Astro Cloud

## Author
Muhammad Muzzamil  
[LinkedIn](https://linkedin.com/in/muzzamil-nagda) · [GitHub](https://github.com/muzzamilanis)
