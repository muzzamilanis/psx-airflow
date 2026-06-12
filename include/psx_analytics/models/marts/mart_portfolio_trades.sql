{{ config(materialized='table') }}

with trades as (
    select * from {{ ref('portfolio_trades') }}
),
buys as (
    select
        broker,
        symbol,
        trade_date                                          as buy_date,
        qty                                                 as buy_qty,
        gross_rate                                          as buy_rate,
        coalesce(comm, 0)
            + coalesce(cdc_amt, 0)
            + coalesce(lsn, 0)
            + coalesce(sst, 0)                             as buy_charges
    from trades
    where trade_type = 'buy'
),
sells as (
    select
        trade_id,
        broker,
        symbol,
        trade_date                                          as sell_date,
        qty                                                 as sell_qty,
        gross_rate                                          as sell_rate,
        coalesce(comm, 0)
            + coalesce(cdc_amt, 0)
            + coalesce(lsn, 0)
            + coalesce(sst, 0)                             as sell_charges,
        reason
    from trades
    where trade_type = 'sell'
),
avg_buy as (
    select
        broker,
        symbol,
        {{ round_numeric(
            'sum(buy_qty * buy_rate) / sum(buy_qty)',
            4
        ) }}                                                as avg_buy_rate,
        sum(buy_qty)                                        as total_buy_qty,
        sum(buy_charges)                                    as total_buy_charges
    from buys
    group by broker, symbol
),
joined as (
    select
        s.trade_id,
        s.broker,
        s.symbol,
        s.sell_date,
        s.sell_qty,
        s.sell_rate,
        b.avg_buy_rate,
        s.sell_qty * s.sell_rate                            as gross_proceeds,
        s.sell_qty * b.avg_buy_rate                         as cost_basis,
        (s.sell_qty * s.sell_rate)
            - (s.sell_qty * b.avg_buy_rate)                 as gross_pnl,
        s.sell_charges
            + (b.total_buy_charges
                * s.sell_qty::numeric
                / b.total_buy_qty::numeric
              )                                             as allocated_charges,
        (s.sell_qty * s.sell_rate)
            - (s.sell_qty * b.avg_buy_rate)
            - s.sell_charges
            - (b.total_buy_charges
                * s.sell_qty::numeric
                / b.total_buy_qty::numeric
              )                                             as net_pnl,
        {{ round_numeric(
            '((s.sell_qty * s.sell_rate) - (s.sell_qty * b.avg_buy_rate)) / (s.sell_qty * b.avg_buy_rate) * 100',
            2
        ) }}                                                as gross_pnl_pct,
        s.reason
    from sells s
    left join avg_buy b
        on s.broker = b.broker
        and s.symbol = b.symbol
)
select * from joined