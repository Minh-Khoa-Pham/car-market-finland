-- Regions (incl. unknown and abroad) must add up to mainland Finland (MA1), per month.
with src as (select * from {{ source('raw', 'registrations') }}
             where brand_code = 'YH' and power_code = 'YH')
select year, month,
       sum(registrations) filter (where region_code <> 'MA1') as by_region,
       sum(registrations) filter (where region_code = 'MA1')  as total
from src
group by 1, 2
having coalesce(by_region, 0) <> coalesce(total, 0)
