-- National market share by brand and month (mainland Finland, excluding motorhomes).
with brand_month as (
    select month_date, brand_code, brand_name, importer_group,
           sum(registrations) as registrations,
           sum(registrations) filter (where powertrain = 'Battery electric') as bev_registrations
    from {{ ref('fct_registrations') }}
    group by all
)

select
    *,
    registrations / sum(registrations) over (partition by month_date) as market_share,
    rank() over (partition by month_date order by registrations desc)  as market_rank,
    lag(registrations, 12) over (partition by brand_code order by month_date) as registrations_prev_year
from brand_month
