{{ config(materialized='table') }}

with cgt as (
    select * from {{ ref('portfolio_cgt_monthly') }}
),
summary as (
    select
        broker,
        period_month,
        sum(coalesce(capital_gain_loss, 0))                 as net_gain_loss,
        sum(coalesce(provisional_cgt, 0))                   as provisional_cgt,
        max(coalesce(cgt_payable_cumulative, 0))            as cgt_payable_cumulative,
        max(coalesce(cgt_collected_cumulative, 0))          as cgt_collected_cumulative,
        max(coalesce(cgt_shortfall, 0))                     as cgt_shortfall,
        max(coalesce(cgt_refund, 0))                        as cgt_refund
    from cgt
    group by broker, period_month
)
select
    broker,
    period_month,
    {{ round_numeric('net_gain_loss', 2) }}                 as net_gain_loss,
    {{ round_numeric('provisional_cgt', 2) }}               as provisional_cgt,
    {{ round_numeric('cgt_payable_cumulative', 2) }}        as cgt_payable_cumulative,
    {{ round_numeric('cgt_collected_cumulative', 2) }}      as cgt_collected_cumulative,
    {{ round_numeric('cgt_shortfall', 2) }}                 as cgt_shortfall,
    {{ round_numeric('cgt_refund', 2) }}                    as cgt_refund,
    {{ round_numeric('cgt_collected_cumulative - cgt_payable_cumulative', 2) }}
                                                            as cgt_over_under_collected
from summary
order by broker, period_month