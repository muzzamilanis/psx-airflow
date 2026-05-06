{{ config(materialized='table') }}

select
    s.fetched_at,
    coalesce(m.sector, 'Unknown') as sector,
    count(distinct s.symbol)      as total_stocks,
    round(avg(s.change_pct), 2)   as avg_change_pct,
    sum(s.volume)                 as total_volume,
    sum(s.market_cap_m)           as total_market_cap_m,
    round(avg(s.current_price), 2) as avg_price
from {{ ref('stg_psx_daily_snapshot') }} s
left join {{ ref('psx_sector_mapping') }} m
    on s.symbol = m.symbol
group by s.fetched_at, coalesce(m.sector, 'Unknown')
order by s.fetched_at, total_market_cap_m desc nulls last