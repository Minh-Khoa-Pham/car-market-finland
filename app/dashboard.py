"""Finnish car market dashboard: K-Auto brands vs the market.

Run:  streamlit run app/dashboard.py
Data: Traficom open data (CC BY 4.0), modelled with dbt into data/car_market.duckdb.
"""

from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "car_market.duckdb"
K_AUTO_COLOR, OTHER_COLOR, MARKET_COLOR = "#1F4E79", "#B8C4D0", "#E07B39"

st.set_page_config(page_title="Finnish Car Market", layout="wide")


@st.cache_data
def query(sql: str) -> pd.DataFrame:
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        return con.execute(sql).df()


k_auto = query("select * from marts.mart_k_auto_monthly order by month_date")
brands = query("select * from marts.mart_brand_monthly")
regions = query("select * from marts.mart_region_yearly")

latest = k_auto.iloc[-1]
year_ago = k_auto[k_auto["month_date"] == latest["month_date"] - pd.DateOffset(years=1)]
latest_label = latest["month_date"].strftime("%B %Y")

st.title("Finnish Car Market: K-Auto brands vs the market")
st.caption(
    "New passenger car registrations in mainland Finland, excluding motorhomes. "
    "K-Auto brands: Volkswagen, Audi, SEAT, CUPRA, Porsche, Bentley."
)

# --- KPI row -----------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric(f"Market, {latest_label}", f"{int(latest['market_total']):,}")
c2.metric(f"K-Auto, {latest_label}", f"{int(latest['k_auto']):,}")
share_delta = (
    f"{100 * (latest['k_auto_share'] - year_ago['k_auto_share'].iloc[0]):+.1f} pp vs year before"
    if not year_ago.empty
    else None
)
c3.metric("K-Auto market share", f"{100 * latest['k_auto_share']:.1f}%", share_delta)
c4.metric(
    "Electric share: K-Auto vs market",
    f"{100 * latest['k_auto_bev_share']:.0f}% vs {100 * latest['market_bev_share']:.0f}%",
)

# --- K-Auto share over time ------------------------------------------------
st.subheader("K-Auto market share over time")
share = k_auto.melt(
    id_vars="month_date",
    value_vars=["k_auto_share", "k_auto_share_rolling_12m"],
    var_name="series",
    value_name="share",
)
share["series"] = share["series"].map(
    {"k_auto_share": "Monthly", "k_auto_share_rolling_12m": "Rolling 12 months"}
)
fig = px.line(
    share, x="month_date", y="share", color="series",
    color_discrete_map={"Monthly": OTHER_COLOR, "Rolling 12 months": K_AUTO_COLOR},
    labels={"month_date": "", "share": "Market share", "series": ""},
)
fig.update_yaxes(tickformat=".0%")
st.plotly_chart(fig, use_container_width=True)

# --- Brand ranking and electric share --------------------------------------
left, right = st.columns(2)
years = sorted(brands["month_date"].dt.year.unique(), reverse=True)
year = left.selectbox("Year", years)

with left:
    st.subheader(f"Top 15 brands, {year}")
    top = (
        brands[brands["month_date"].dt.year == year]
        .groupby(["brand_name", "importer_group"], as_index=False)["registrations"].sum()
        .nlargest(15, "registrations")
        .sort_values("registrations")
    )
    fig = px.bar(
        top, x="registrations", y="brand_name", color="importer_group", orientation="h",
        color_discrete_map={"K-Auto": K_AUTO_COLOR, "Other": OTHER_COLOR},
        labels={"registrations": "Registrations", "brand_name": "", "importer_group": ""},
    )
    fig.update_yaxes(categoryorder="total ascending")  # keep bars sorted across both colours
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Electric car share")
    bev = k_auto.melt(
        id_vars="month_date",
        value_vars=["k_auto_bev_share", "market_bev_share"],
        var_name="series",
        value_name="share",
    )
    bev["series"] = bev["series"].map(
        {"k_auto_bev_share": "K-Auto", "market_bev_share": "Whole market"}
    )
    fig = px.line(
        bev, x="month_date", y="share", color="series",
        color_discrete_map={"K-Auto": K_AUTO_COLOR, "Whole market": MARKET_COLOR},
        labels={"month_date": "", "share": "Battery electric share", "series": ""},
    )
    fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(fig, use_container_width=True)

# --- Regions ------------------------------------------------------------------
st.subheader(f"K-Auto share by region, {year}")
reg = regions[regions["year"] == year].sort_values("k_auto_share")
fig = px.bar(
    reg, x="k_auto_share", y="region_name", orientation="h",
    color_discrete_sequence=[K_AUTO_COLOR],
    hover_data={"market_total": ":,", "k_auto": ":,"},
    labels={"k_auto_share": "K-Auto share", "region_name": ""},
)
fig.update_xaxes(tickformat=".0%")
st.plotly_chart(fig, use_container_width=True)

st.caption(
    "Source: Traficom, first registrations of passenger cars (table 010_ensirek_tau_101), "
    "CC BY 4.0. Independent portfolio project, not affiliated with Kesko or K-Auto."
)
