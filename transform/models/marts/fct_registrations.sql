-- Passenger car first registrations, excluding motorhomes.
-- Grain: month x region x brand x power source.
select
    r.month_date,
    r.year,
    r.month,
    r.region_code,
    r.region_name,
    r.brand_code,
    b.brand_name,
    b.importer_group,
    r.power_code,
    p.power_name_en,
    p.powertrain,
    r.registrations
from {{ ref('stg_registrations') }} r
join {{ ref('dim_brand') }} b using (brand_code)
join {{ ref('powertrains') }} p using (power_code)
