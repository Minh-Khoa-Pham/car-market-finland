select distinct
    r.brand_code,
    r.brand_name,
    coalesce(g.importer_group, 'Other') as importer_group
from {{ ref('stg_registrations') }} r
left join {{ ref('brand_groups') }} g
    on upper(r.brand_name) = g.brand_name
