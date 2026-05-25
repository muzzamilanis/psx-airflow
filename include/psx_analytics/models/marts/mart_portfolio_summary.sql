{{ config(materialized='table') }}

with snapshot as (
    select * from {{ ref('mart_portfolio_snapshot') }}
)

select
    price_date,
    sum(total_cost)                                         as total_invested,
    sum(current_value)                                      as total_current_value,
    sum(unrealized_pnl)                                     as total_unrealized_pnl,
    {{ round_numeric(
        'sum(unrealized_pnl) / sum(total_cost) * 100',
        2
    ) }}                                                    as total_unrealized_pct,
    count(symbol)                                           as holdings_count
from snapshot
group by price_date
