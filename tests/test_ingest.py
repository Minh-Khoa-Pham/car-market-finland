"""Unit tests for the ingestion helpers. They use a tiny hand-made json-stat2
response, so they run without network access."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingest"))

import fetch_registrations as fr  # noqa: E402


def _dim(codes_labels):
    return {
        "category": {
            "index": {code: i for i, (code, _) in enumerate(codes_labels)},
            "label": dict(codes_labels),
        }
    }


SAMPLE = {
    "id": [fr.REGION, fr.BRAND, fr.POWER, fr.YEAR, fr.MONTH],
    "dimension": {
        fr.REGION: _dim([("MK01", "Uusimaa")]),
        fr.BRAND: _dim([("267", "Volkswagen"), ("905", "Toyota")]),
        fr.POWER: _dim([("04", "Sähkö")]),
        fr.YEAR: _dim([("2025", "2025")]),
        fr.MONTH: _dim([("01", "Tammikuu"), ("02", "Helmikuu")]),
    },
    # Row-major order: brand varies slower than month.
    "value": [10, None, 7, 3],
}


def test_jsonstat_is_flattened_in_row_major_order():
    df = fr.to_raw_schema(fr.jsonstat_to_frame(SAMPLE))
    assert len(df) == 4
    vw_feb = df[(df.brand_name == "Volkswagen") & (df.month == 2)]
    toyota_jan = df[(df.brand_name == "Toyota") & (df.month == 1)]
    assert vw_feb.registrations.isna().all()  # missing value is kept as null
    assert toyota_jan.registrations.iloc[0] == 7
    assert set(df.columns) >= {"region_code", "brand_code", "power_code", "year", "month"}


def test_requests_stay_under_the_api_cell_limit():
    meta = {
        fr.REGION: {f"R{i}": "" for i in range(21)},
        fr.BRAND: {f"B{i}": "" for i in range(76)},
        fr.POWER: {f"P{i}": "" for i in range(11)},
        fr.YEAR: {"2025": "", "2026": ""},
        fr.MONTH: {"SS": "", **{f"{m:02d}": "" for m in range(1, 13)}},
    }
    chunks = fr.plan_requests(meta, ["2025", "2026"])
    for chunk in chunks:
        cells = 1
        for values in chunk.values():
            cells *= len(values)
        assert cells <= fr.MAX_CELLS
    assert "SS" not in chunks[0][fr.MONTH]  # yearly total is excluded
    covered = {(r, c[fr.YEAR][0]) for c in chunks for r in c[fr.REGION]}
    assert len(covered) == 21 * 2  # every region-year is fetched exactly once
