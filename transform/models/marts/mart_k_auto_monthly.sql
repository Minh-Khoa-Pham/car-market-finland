-- K-Auto brands vs the whole market, by month.
with monthly as (
    select
        month_date,
        sum(registrations)                                                   as market_total,
        sum(registrations) filter (where importer_group = 'K-Auto')           as k_auto,
        sum(registrations) filter (where powertrain = 'Battery electric')      as market_bev,
        sum(registrations) filter (where importer_group = 'K-Auto'
                                     and powertrain = 'Battery electric')      as k_auto_bev
    from {{ ref('fct_registrations') }}
    group by 1
)

select
    month_date,
    market_total,
    k_auto,
    k_auto / market_total                                  as k_auto_share,
    market_bev / market_total                              as market_bev_share,
    k_auto_bev / nullif(k_auto, 0)                         as k_auto_bev_share,
    case when count(*) over w12 = 12
         then sum(k_auto) over w12 / sum(market_total) over w12
    end                                                    as k_auto_share_rolling_12m  -- only with a full 12 months
from monthly
window w12 as (order by month_date rows between 11 preceding and current row)
