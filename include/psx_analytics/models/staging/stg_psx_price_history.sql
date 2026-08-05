{{ config(materialized='view') }}

select
    id,
    symbol,
    price_date,
    open,
    high,
    low,
    close,
    volume,
    dividends,
    stock_splits,
    fetched_at
from {{ source('raw', 'psx_price_history') }}
