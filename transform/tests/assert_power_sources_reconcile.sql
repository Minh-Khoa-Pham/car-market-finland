-- Detail power sources must add up to the source's own all-power total, per month.
with src as (select * from {{ source('raw', 'registrations') }}
             where region_code = 'MA1' and brand_code = 'YH')
select year, month,
       sum(registrations) filter (where power_code <> 'YH') as by_power,
       sum(registrations) filter (where power_code = 'YH')  as total
from src
group by 1, 2
having coalesce(by_power, 0) <> coalesce(total, 0)
