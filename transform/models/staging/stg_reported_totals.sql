-- Totals as published by Traficom, used to reconcile our own sums in tests.
select
    make_date(year, month, 1)                         as month_date,
    sum(registrations) filter (where brand_code = 'YH')   as reported_total,
    sum(registrations) filter (where brand_code = 'MATK') as reported_motorhomes
from {{ source('raw', 'registrations') }}
where region_code = 'MA1'
  and power_code = 'YH'
  and brand_code in ('YH', 'MATK')
group by 1
