-- Detail rows only: one row per month x region x brand x power source.
-- The source's own total rows are kept separately in stg_reported_totals.
with source as (
    select * from {{ source('raw', 'registrations') }}
)

select
    make_date(year, month, 1)        as month_date,
    year,
    month,
    region_code,
    region_name,
    brand_code,
    case when brand_code = 'MUUT' then 'Other brands' else brand_name end as brand_name,
    power_code,
    cast(registrations as integer)   as registrations
from source
where region_code <> 'MA1'                       -- MA1 = mainland Finland total
  and brand_code not in ('YH', 'MATK')           -- YH = all cars, MATK = motorhomes
  and power_code <> 'YH'                         -- YH = all power sources
