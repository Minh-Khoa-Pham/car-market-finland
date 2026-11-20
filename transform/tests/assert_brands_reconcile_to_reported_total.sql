-- Our brand-level sum must equal Traficom's published total minus motorhomes.
-- Returns the months where the numbers don't match (a passing test returns no rows).
with ours as (
    select month_date, sum(registrations) as our_total
    from {{ ref('fct_registrations') }}
    group by 1
)
select t.month_date, o.our_total, t.reported_total, t.reported_motorhomes
from {{ ref('stg_reported_totals') }} t
left join ours o using (month_date)
where coalesce(o.our_total, 0) <> t.reported_total - coalesce(t.reported_motorhomes, 0)
