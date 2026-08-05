{{ config(materialized='table') }}

with price_history as (
    select
        symbol,
        price_date,
        high,
        low,
        close,
        volume
    from {{ ref('stg_psx_price_history') }}
    where close is not null
),

with_change as (
    select
        symbol,
        price_date,
        high,
        low,
        close,
        volume,
        close - lag(close) over (partition by symbol order by price_date) as price_change
    from price_history
),

windowed as (
    select
        symbol,
        price_date,
        close,
        volume,

        avg(close) over sma_50_window   as sma_50,
        count(close) over sma_50_window as sma_50_days,

        avg(close) over sma_200_window   as sma_200,
        count(close) over sma_200_window as sma_200_days,

        -- 52 weeks of trading days, approximated as the trailing 252 rows
        max(high) over week_52_window as high_52w,
        min(low) over week_52_window  as low_52w,

        avg(volume) over vol_20_window   as avg_volume_20,
        count(volume) over vol_20_window as avg_volume_20_days,

        avg(case when price_change > 0 then price_change else 0 end) over rsi_14_window as avg_gain_14,
        avg(case when price_change < 0 then -price_change else 0 end) over rsi_14_window as avg_loss_14,
        count(price_change) over rsi_14_window                                          as rsi_14_days,

        row_number() over (partition by symbol order by price_date desc) as rn

    from with_change
    window
        sma_50_window as (partition by symbol order by price_date rows between 49 preceding and current row),
        sma_200_window as (partition by symbol order by price_date rows between 199 preceding and current row),
        week_52_window as (partition by symbol order by price_date rows between 251 preceding and current row),
        vol_20_window as (partition by symbol order by price_date rows between 19 preceding and current row),
        rsi_14_window as (partition by symbol order by price_date rows between 13 preceding and current row)
),

latest as (
    select *
    from windowed
    where rn = 1
)

select
    symbol,
    price_date,
    close,
    volume,

    case when sma_50_days = 50 then round(sma_50, 4) end as sma_50,
    case when sma_50_days = 50
        then round(100 * (close - sma_50) / nullif(sma_50, 0), 2)
    end as pct_vs_sma_50,

    case when sma_200_days = 200 then round(sma_200, 4) end as sma_200,
    case when sma_200_days = 200
        then round(100 * (close - sma_200) / nullif(sma_200, 0), 2)
    end as pct_vs_sma_200,

    case when rsi_14_days = 14
        then case
            when coalesce(avg_loss_14, 0) = 0 then 100
            else round(100 - (100 / (1 + (avg_gain_14 / avg_loss_14))), 2)
        end
    end as rsi_14,

    round(high_52w, 4) as high_52w,
    round(low_52w, 4) as low_52w,
    round(100 * (close - high_52w) / nullif(high_52w, 0), 2) as pct_vs_high_52w,

    case when avg_volume_20_days = 20 then round(avg_volume_20, 2) end as avg_volume_20,
    case when avg_volume_20_days = 20
        then round(volume / nullif(avg_volume_20, 0), 2)
    end as volume_ratio_20

from latest
order by symbol
