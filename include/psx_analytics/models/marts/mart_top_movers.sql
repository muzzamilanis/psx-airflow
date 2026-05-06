{{ config(materialized='table') }}

select
    fetched_at,
    symbol,
    name,
    ldcp,
    current_price,
    change_amount,
    change_pct,
    volume,
    market_cap_m
from {{ ref('stg_psx_daily_snapshot') }}
where change_pct is not null
order by change_pct desc