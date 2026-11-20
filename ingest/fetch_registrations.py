"""Load Finnish passenger car first registrations from Traficom's open statistics API.

Source: Traficom, table 010_ensirek_tau_101 ("Henkilöautojen ensirekisteröinnit"),
monthly first registrations by region (maakunta), brand (merkki), power source
(käyttövoima), year and month. Licence: CC BY 4.0.

The API returns at most 110,000 cells per request, so the data is fetched one year
and one group of regions at a time, then written to DuckDB as raw.registrations.

Usage:
    python ingest/fetch_registrations.py                 # all years
    python ingest/fetch_registrations.py --years 2025 2026
"""

from __future__ import annotations

import argparse
import itertools
import time
from pathlib import Path

import duckdb
import pandas as pd
import requests

API_URL = (
    "https://trafi2.stat.fi/PXWeb/api/v1/fi/TraFi/"
    "Ensirekisteroinnit/010_ensirek_tau_101.px"
)
MAX_CELLS = 110_000
DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "car_market.duckdb"

# Variable codes in the source table (Finnish names kept as in the API).
REGION, BRAND, POWER, YEAR, MONTH = "Maakunta", "Merkki", "Käyttövoima", "Vuosi", "Kuukausi"


def get_metadata(session: requests.Session) -> dict[str, dict[str, str]]:
    """Return {variable_code: {value_code: value_label}} for the table."""
    resp = session.get(API_URL, timeout=60)
    resp.raise_for_status()
    return {
        v["code"]: dict(zip(v["values"], v["valueTexts"]))
        for v in resp.json()["variables"]
    }


def plan_requests(meta: dict[str, dict[str, str]], years: list[str]) -> list[dict]:
    """Split the full query into chunks that stay under the API's cell limit."""
    months = [m for m in meta[MONTH] if m != "SS"]  # skip the yearly total; we sum ourselves
    regions = list(meta[REGION])
    cells_per_region = len(meta[BRAND]) * len(meta[POWER]) * len(months)
    regions_per_call = max(1, MAX_CELLS // cells_per_region)

    chunks = []
    for year in years:
        for i in range(0, len(regions), regions_per_call):
            chunks.append(
                {
                    REGION: regions[i : i + regions_per_call],
                    BRAND: list(meta[BRAND]),
                    POWER: list(meta[POWER]),
                    YEAR: [year],
                    MONTH: months,
                }
            )
    return chunks


def fetch_chunk(session: requests.Session, selection: dict[str, list[str]]) -> dict:
    query = {
        "query": [
            {"code": code, "selection": {"filter": "item", "values": values}}
            for code, values in selection.items()
        ],
        "response": {"format": "json-stat2"},
    }
    for attempt in range(4):
        resp = session.post(API_URL, json=query, timeout=120)
        if resp.status_code == 429:  # rate limited: back off and retry
            time.sleep(10 * (attempt + 1))
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()
    return {}


def jsonstat_to_frame(js: dict) -> pd.DataFrame:
    """Flatten a json-stat2 dataset into one row per cell (codes and labels)."""
    dims = js["id"]
    categories = []
    for dim in dims:
        cat = js["dimension"][dim]["category"]
        codes = sorted(cat["index"], key=cat["index"].get)
        categories.append([(code, cat["label"][code]) for code in codes])

    values = js["value"]
    rows = []
    for combo, value in zip(itertools.product(*categories), values):
        row = {}
        for dim, (code, label) in zip(dims, combo):
            row[f"{dim}_code"] = code
            row[f"{dim}_label"] = label
        row["registrations"] = value  # None when the API has no value (e.g. future months)
        rows.append(row)
    return pd.DataFrame(rows)


def to_raw_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Rename source columns to stable English names for the raw table."""
    return pd.DataFrame(
        {
            "region_code": df[f"{REGION}_code"],
            "region_name": df[f"{REGION}_label"],
            "brand_code": df[f"{BRAND}_code"],
            "brand_name": df[f"{BRAND}_label"],
            "power_code": df[f"{POWER}_code"],
            "power_name": df[f"{POWER}_label"],
            "year": df[f"{YEAR}_code"].astype(int),
            "month": df[f"{MONTH}_code"].astype(int),
            "registrations": df["registrations"],
        }
    )


def load(db_path: Path, frame: pd.DataFrame, years: list[str]) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.execute("create schema if not exists raw")
    con.execute(
        """
        create table if not exists raw.registrations (
            region_code varchar, region_name varchar,
            brand_code varchar, brand_name varchar,
            power_code varchar, power_name varchar,
            year integer, month integer, registrations double,
            loaded_at timestamp
        )
        """
    )
    # Reload only the requested years so the script is safe to re-run.
    con.execute(
        "delete from raw.registrations where year in (select unnest(?))",
        [[int(y) for y in years]],
    )
    con.register("incoming", frame)
    con.execute(
        "insert into raw.registrations select *, current_timestamp from incoming"
    )
    con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--years", nargs="*", help="years to load (default: all)")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    session = requests.Session()
    meta = get_metadata(session)
    years = args.years or list(meta[YEAR])
    chunks = plan_requests(meta, years)
    print(f"Fetching {len(years)} year(s) in {len(chunks)} request(s)...")

    frames = []
    for n, selection in enumerate(chunks, 1):
        frames.append(to_raw_schema(jsonstat_to_frame(fetch_chunk(session, selection))))
        print(f"  {n}/{len(chunks)} done", end="\r")
        time.sleep(0.5)  # stay well under the API's 100 calls / 10 s limit

    data = pd.concat(frames, ignore_index=True)
    data = data[data["registrations"].notna()]  # drop months not published yet
    load(args.db, data, years)
    print(f"\nLoaded {len(data):,} rows into {args.db} (raw.registrations)")


if __name__ == "__main__":
    main()
