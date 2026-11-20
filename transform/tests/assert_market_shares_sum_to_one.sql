select month_date, sum(market_share) as total_share
from {{ ref('mart_brand_monthly') }}
group by 1
having abs(sum(market_share) - 1) > 1e-9
