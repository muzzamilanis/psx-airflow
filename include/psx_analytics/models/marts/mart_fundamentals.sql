{{ config(materialized='table') }}

with fundamentals as (
    select * from {{ ref('fundamentals_snapshot') }}
),

latest_date as (
    select max({{ cast_date('fetched_at') }}) as max_date
    from {{ ref('stg_psx_daily_snapshot') }}
),

latest_prices as (
    select
        s.symbol,
        s.current_price,
        {{ cast_date('s.fetched_at') }} as price_date
    from {{ ref('stg_psx_daily_snapshot') }} s
    inner join latest_date d
        on {{ cast_date('s.fetched_at') }} = d.max_date
)

select
    f.symbol,
    f.company_name,
    f.sector,
    f.fy_end_month,
    f.latest_fy,
    f.latest_fy_sales_000,
    f.latest_fy_pat_000,
    f.latest_fy_eps,
    f.prior_fy_eps,
    f.fy_eps_growth_pct,
    f.fy_gpm_pct,
    f.fy_npm_pct,
    f.latest_qtr,
    f.latest_qtr_sales_000,
    f.latest_qtr_pat_000,
    f.latest_qtr_eps,
    f.pe_ttm as pe_ttm_psx,
    f.last_result_title_date,
    f.results_stale_flag,
    f.notes,
    p.current_price,
    p.price_date,
    case
        when f.latest_fy_eps is null or f.latest_fy_eps = 0 then null
        else {{ round_numeric('p.current_price / f.latest_fy_eps', 2) }}
    end as pe_using_fy_eps
from fundamentals f
left join latest_prices p
    on f.symbol = p.symbol
order by f.symbol
