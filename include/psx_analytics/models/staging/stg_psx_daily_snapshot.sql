{{ config(materialized='view') }}

with cleaned as (
    select
        id,
        fetched_at,
        symbol,
        name,
        replace(trim(ldcp), ',', '')                                        as ldcp_clean,
        replace(trim({{ quote_column('current') }}), ',', '')               as current_clean,
        replace(trim(change), ',', '')                                      as change_clean,
        replace(replace(trim(change_1), '%', ''), ',', '')                  as change_pct_clean,
        replace(replace(trim(idx_wtg), '%', ''), ',', '')                   as idx_wtg_clean,
        replace(trim(idx_point), ',', '')                                   as idx_point_clean,
        replace(trim(volume), ',', '')                                      as volume_clean,
        replace(trim(shares_m), ',', '')                                    as shares_clean,
        replace(trim(market_cap_m), ',', '')                                as market_cap_clean,
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
    {{ safe_cast('ldcp_clean', 'numeric') }}        as ldcp,
    {{ safe_cast('current_clean', 'numeric') }}     as current_price,
    {{ safe_cast('change_clean', 'numeric') }}      as change_amount,
    {{ safe_cast('change_pct_clean', 'numeric') }}  as change_pct,
    {{ safe_cast('idx_wtg_clean', 'numeric') }}     as idx_weight,
    {{ safe_cast('idx_point_clean', 'numeric') }}   as idx_point,
    {{ safe_cast('volume_clean', 'numeric') }}      as volume,
    {{ safe_cast('shares_clean', 'numeric') }}      as shares_m,
    {{ safe_cast('market_cap_clean', 'numeric') }}  as market_cap_m
from cleaned
where rn = 1
  and not (symbol = 'ENGRO' and ldcp_clean = '285.50' and current_clean = '287.00')
  and not (symbol = 'LUCK'  and ldcp_clean = '920.00' and current_clean = '915.00')
  and not (symbol = 'HBL'   and ldcp_clean = '145.00' and current_clean = '146.50')
  and not (symbol = 'PSO'   and ldcp_clean = '310.00' and current_clean = '308.00')
  and not (symbol = 'TRG'   and ldcp_clean = '98.50'  and current_clean = '99.00')
