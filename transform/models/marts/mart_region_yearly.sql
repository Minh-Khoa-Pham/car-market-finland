-- K-Auto share by region (maakunta) and year.
select
    year,
    region_code,
    region_name,
    sum(registrations)                                                  as market_total,
    sum(registrations) filter (where importer_group = 'K-Auto')          as k_auto,
    sum(registrations) filter (where importer_group = 'K-Auto')
        / nullif(sum(registrations), 0)                                 as k_auto_share
from {{ ref('fct_registrations') }}
where region_code not in ('MKTT', 'MKUU')   -- unknown region / abroad
group by all
