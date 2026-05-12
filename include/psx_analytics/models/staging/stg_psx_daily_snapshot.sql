{{ config(materialized='view') }}

with cleaned as (
    select
        id,
        fetched_at,
        symbol,
        name,
        replace(trim(ldcp), ',', '')                            as ldcp_clean,
        replace(trim(current), ',', '')                         as current_clean,
        replace(trim(change), ',', '')                          as change_clean,
        replace(replace(trim(change_1), '%', ''), ',', '')      as change_pct_clean,
        replace(replace(trim(idx_wtg), '%', ''), ',', '')       as idx_wtg_clean,
        replace(trim(idx_point), ',', '')                       as idx_point_clean,
        replace(trim(volume), ',', '')                          as volume_clean,
        replace(trim(shares_m), ',', '')                        as shares_clean,
        replace(trim(market_cap_m), ',', '')                    as market_cap_clean,
        row_number() over (
            partition by fetched_at, symbol
            order by id desc
        ) as rn
    from {{ source('raw', 'PsxAllShr') }}
)

select
    id,
    fetched_at,
    symbol,
    name,
    nullif(ldcp_clean, '')::numeric         as ldcp,
    nullif(current_clean, '')::numeric      as current_price,
    nullif(change_clean, '')::numeric       as change_amount,
    nullif(change_pct_clean, '')::numeric   as change_pct,
    nullif(idx_wtg_clean, '')::numeric      as idx_weight,
    nullif(idx_point_clean, '')::numeric    as idx_point,
    nullif(volume_clean, '')::bigint        as volume,
    nullif(shares_clean, '')::numeric       as shares_m,
    nullif(market_cap_clean, '')::numeric   as market_cap_m
from cleaned
where rn = 1
    -- Exclude hardcoded mock data rows injected during pipeline development and testing.
    -- These five records were manually inserted to validate the pipeline end-to-end
    -- before the live scraper was connected. Filtered by exact symbol + price combination
    -- to avoid impacting legitimate future trades at similar price points.
  and not (symbol = 'ENGRO' and ldcp_clean = '285.50' and current_clean = '287.00')
  and not (symbol = 'LUCK'  and ldcp_clean = '920.00' and current_clean = '915.00')
  and not (symbol = 'HBL'   and ldcp_clean = '145.00' and current_clean = '146.50')
  and not (symbol = 'PSO'   and ldcp_clean = '310.00' and current_clean = '308.00')
  and not (symbol = 'TRG'   and ldcp_clean = '98.50'  and current_clean = '99.00')
