{{ config(materialized='table') }}

with holdings as (
    select * from {{ ref('portfolio_holdings') }}
),

latest_date as (
    select max({{ cast_date('fetched_at') }}) as max_date
    from {{ ref('stg_psx_daily_snapshot') }}
),

latest_prices as (
    select
        s.symbol,
        s.current_price,
        s.change_pct,
        {{ cast_date('s.fetched_at') }} as price_date
    from {{ ref('stg_psx_daily_snapshot') }} s
    inner join latest_date d
        on {{ cast_date('s.fetched_at') }} = d.max_date
),

joined as (
    select
        h.symbol,
        h.sector,
        h.qty_held,
        h.avg_buy_rate,
        h.qty_held * h.avg_buy_rate                         as total_cost,
        p.current_price,
        p.change_pct                                        as todays_change_pct,
        h.qty_held * p.current_price                        as current_value,
        (h.qty_held * p.current_price)
            - (h.qty_held * h.avg_buy_rate)                 as unrealized_pnl,
        {{ round_numeric(
            '(p.current_price - h.avg_buy_rate) / h.avg_buy_rate * 100',
            2
        ) }}                                                as unrealized_pct,
        p.price_date
    from holdings h
    left join latest_prices p on h.symbol = p.symbol
)

select * from joined
