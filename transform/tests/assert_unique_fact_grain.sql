select month_date, region_code, brand_code, power_code, count(*) as n
from {{ ref('fct_registrations') }}
group by all
having count(*) > 1
