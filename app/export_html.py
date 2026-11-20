"""Export a self-contained HTML sales dashboard (docs/index.html) from the dbt marts.

Run after `dbt build`:  python app/export_html.py
The page embeds its data and Chart.js, so it works offline and on GitHub Pages.
"""

import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "car_market.duckdb"
TEMPLATE = ROOT / "app" / "dashboard_template.html"
CHART_JS = ROOT / "app" / "vendor" / "chart.umd.js"
OUT = ROOT / "docs" / "index.html"


def rows(con, sql):
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def main():
    con = duckdb.connect(str(DB), read_only=True)
    latest = con.execute("select max(month_date) from marts.fct_registrations").fetchone()[0]
    y, m = latest.year, latest.month

    monthly = rows(con, """
        select strftime(month_date, '%Y-%m') as m, market_total as market, k_auto as k,
               round(market_bev_share, 4) as bev_m, round(k_auto_bev_share, 4) as bev_k
        from marts.mart_k_auto_monthly order by month_date""")
    months = [r["m"] for r in monthly]

    # Brands to show: top 15 of the last 12 months plus every K-Auto brand.
    brands = [r["brand_name"] for r in rows(con, f"""
        select brand_name from marts.fct_registrations
        where month_date > date '{latest}' - interval 12 month
        group by brand_name, importer_group
        qualify rank() over (order by sum(registrations) desc) <= 15 or importer_group = 'K-Auto'
        order by sum(registrations) desc""")]
    k_auto_brands = [r["brand_name"] for r in rows(con,
        "select brand_name from marts.dim_brand where importer_group = 'K-Auto'")]

    bm = rows(con, """select brand_name, strftime(month_date, '%Y-%m') as m, registrations
                      from marts.mart_brand_monthly""")
    series = {b: [0] * len(months) for b in brands}
    idx = {mm: i for i, mm in enumerate(months)}
    for r in bm:
        if r["brand_name"] in series:
            series[r["brand_name"]][idx[r["m"]]] = int(r["registrations"])

    # Year-to-date scorecard: same months this year vs last year.
    ytd = rows(con, f"""
        with b as (
            select brand_name, importer_group,
                   sum(registrations) filter (where year = {y})     as ytd,
                   sum(registrations) filter (where year = {y - 1}) as ytd_prev
            from marts.fct_registrations where month <= {m} and year in ({y}, {y - 1})
            group by all)
        select *, ytd / sum(ytd) over () as share, ytd_prev / sum(ytd_prev) over () as share_prev
        from b""")
    ytd_market = sum(r["ytd"] or 0 for r in ytd)
    ytd_market_prev = sum(r["ytd_prev"] or 0 for r in ytd)

    mix = rows(con, """
        select year, powertrain,
               sum(registrations) as market,
               sum(registrations) filter (where importer_group = 'K-Auto') as k
        from marts.fct_registrations group by all order by year""")

    regions = rows(con, f"""
        select region_name,
               sum(registrations) filter (where year = {y}) as market,
               sum(registrations) filter (where year = {y} and importer_group = 'K-Auto') as k,
               sum(registrations) filter (where year = {y - 1}) as market_prev,
               sum(registrations) filter (where year = {y - 1} and importer_group = 'K-Auto') as k_prev
        from marts.fct_registrations
        where month <= {m} and year in ({y}, {y - 1}) and region_code not in ('MKTT', 'MKUU')
        group by 1""")

    data = {
        "latest": {"year": y, "month": m, "label": latest.strftime("%B %Y")},
        "months": months, "monthly": monthly,
        "brands": brands, "kAutoBrands": k_auto_brands, "brandSeries": series,
        "ytd": [{k: (float(v) if isinstance(v, (int, float)) and v is not None else v) for k, v in r.items()} for r in ytd],
        "ytdMarket": ytd_market, "ytdMarketPrev": ytd_market_prev,
        "mix": [{k: (int(v) if k in ("market", "k", "year") and v is not None else v) for k, v in r.items()} for r in mix],
        "regions": [{k: (int(v) if k != "region_name" and v is not None else v) for k, v in r.items()} for r in regions],
    }
    html = (TEMPLATE.read_text(encoding="utf-8")
            .replace("/*__CHARTJS__*/", CHART_JS.read_text(encoding="utf-8"))
            .replace("__DATA__", json.dumps(data, default=str, separators=(",", ":"))))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB), data up to {data['latest']['label']}")


if __name__ == "__main__":
    main()
