"""Market-size comparison table and 10y growth-rate comparison (slide 2,
right panel: the "hidden in plain sight" scale graphic).

CLO outstanding reuses Section 4's dated citation (config.FED_CLO_HOLDER_CITATION,
via data/final/clo_holder_composition.parquet) rather than a live series — no
free current CLO-outstanding figure exists (see scrape_market_size.py
docstring). Because that figure is Dec-2018 while the FRED comparators are
current, the table keeps an explicit `as_of` column per row rather than
implying a single common date; the ratio column is still meaningful (a highly
conservative one, since the other markets have grown since 2018 too) and the
notebook/ledger states the vintage mismatch plainly.

Also derives two TO-VERIFY citations found in the already-cached Section 6
regulator-report corpus (data/interim/regulator_reports.parquet), used as
prose anchors rather than plotted values:
  - "CLOs fund more than 50 percent of outstanding institutional leveraged
    loans" (Fed Financial Stability Report, Nov 2020).
  - Leveraged loans + high-yield bonds outstanding "approximately $1.4
    trillion" as of 2021:Q4 (Fed Financial Stability Report, May 2023, citing
    SEC Form PF / Refinitiv LPC).
No CAGR is computed for CLO outstanding itself — a single dated snapshot has
no second point to grow from; that gap is reported, not filled.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.macro.analysis_scale")

MARKET_SIZE_PATH = config.INTERIM_DIR / "macro_market_size_series.parquet"
CLO_HOLDERS_PATH = config.FINAL_DIR / "clo_holder_composition.parquet"
REGULATOR_REPORTS_PATH = config.INTERIM_DIR / "regulator_reports.parquet"

OUT_COMPARISON = config.FINAL_DIR / "macro_market_size_comparison.parquet"
OUT_GROWTH = config.FINAL_DIR / "macro_market_size_growth_10y.parquet"
OUT_CITATIONS = config.FINAL_DIR / "macro_scale_citations.parquet"

MARKET_SIZE_LABELS = {
    "corporate_and_foreign_bonds": "Corporate & foreign bonds",
    "treasury_total_public_debt": "U.S. Treasury debt",
    "municipal_securities": "Municipal securities",
    "agency_mbs_pools": "Agency/GSE-backed mortgage pools",
}

# Prose anchors sourced from Section 6's already-cached regulator-report text
# (data/interim/regulator_reports.parquet); every value here is a citation,
# not something this repo computed, hence TO-VERIFY.
SCALE_CITATIONS = [
    {
        "claim": "CLOs fund more than 50% of outstanding institutional leveraged loans",
        "value": 0.50, "unit": "share_of_institutional_leveraged_loans",
        "source": "Federal Reserve Financial Stability Report, November 2020",
        "as_of": "2020-11-09", "to_verify": True,
    },
    {
        "claim": "Outstanding institutional leveraged loans + high-yield bonds ~= $1.4 trillion (2021:Q4)",
        "value": 1.4e12, "unit": "usd",
        "source": "Federal Reserve Financial Stability Report, May 2023 (citing SEC Form PF / Refinitiv LPC)",
        "as_of": "2021-12-31", "to_verify": True,
    },
]


def _load_market_size_latest() -> pd.DataFrame:
    if not MARKET_SIZE_PATH.exists():
        return pd.DataFrame(columns=["series", "value_usd_millions", "as_of"])
    df = read_parquet(MARKET_SIZE_PATH)
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna(subset=["value"]).sort_values("date")
    latest = df.groupby("series").tail(1)
    return latest.rename(columns={"value": "value_usd_millions", "date": "as_of"})[["series", "value_usd_millions", "as_of"]]


def _load_clo_outstanding() -> tuple[float, str]:
    """CLO securities held by U.S. investors, Dec 2018 (Section 4 citation).
    Returns (amount_usd_millions, as_of) or (None, None) if unavailable."""
    if not CLO_HOLDERS_PATH.exists():
        logger.warning("no clo_holder_composition.parquet cached; run src.official.scrape_efa/analysis_holders first")
        return None, None
    holders = read_parquet(CLO_HOLDERS_PATH)
    total = holders["amount_usd_millions"].sum()
    as_of = config.FED_CLO_HOLDER_CITATION["as_of"]
    return float(total), as_of


def market_size_comparison() -> pd.DataFrame:
    latest = _load_market_size_latest()
    clo_total, clo_as_of = _load_clo_outstanding()

    rows = []
    if clo_total is not None:
        rows.append({"market": "CLOs (held by U.S. investors)", "value_usd_millions": clo_total,
                      "as_of": clo_as_of, "to_verify": True})
    for series, label in MARKET_SIZE_LABELS.items():
        match = latest[latest["series"] == series]
        if match.empty:
            continue
        rows.append({"market": label, "value_usd_millions": match.iloc[0]["value_usd_millions"],
                      "as_of": str(match.iloc[0]["as_of"].date()), "to_verify": False})

    out = pd.DataFrame(rows)
    if out.empty:
        logger.warning("no market-size data available; market_size_comparison is empty")
        return pd.DataFrame(columns=["market", "value_usd_millions", "as_of", "to_verify", "x_times_clo"])
    clo_row = out[out["market"].str.startswith("CLOs")]
    clo_value = clo_row.iloc[0]["value_usd_millions"] if len(clo_row) else None
    out["x_times_clo"] = (out["value_usd_millions"] / clo_value) if clo_value else None
    return out.sort_values("value_usd_millions", ascending=False).reset_index(drop=True)


def growth_10y() -> pd.DataFrame:
    """10y CAGR for each FRED-sourced comparator. CLO has no second data
    point (single dated snapshot) so it is reported as not-computable rather
    than omitted silently."""
    if not MARKET_SIZE_PATH.exists():
        return pd.DataFrame(columns=["market", "cagr_10y", "start_date", "end_date"])
    df = read_parquet(MARKET_SIZE_PATH)
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna(subset=["value"])

    rows = []
    for series, label in MARKET_SIZE_LABELS.items():
        sub = df[df["series"] == series].sort_values("date")
        if sub.empty:
            continue
        end_date, end_value = sub["date"].iloc[-1], sub["value"].iloc[-1]
        start_cutoff = end_date - pd.DateOffset(years=10)
        start_candidates = sub[sub["date"] <= start_cutoff]
        if start_candidates.empty:
            continue
        start_date, start_value = start_candidates["date"].iloc[-1], start_candidates["value"].iloc[-1]
        years = (end_date - start_date).days / 365.25
        cagr = (end_value / start_value) ** (1 / years) - 1 if start_value > 0 and years > 0 else None
        rows.append({"market": label, "cagr_10y": cagr, "start_date": start_date, "end_date": end_date})

    rows.append({"market": "CLOs (held by U.S. investors)", "cagr_10y": None, "start_date": None, "end_date": None})
    out = pd.DataFrame(rows)
    logger.info("CLO 10y CAGR not computable: single dated snapshot (Dec 2018), no second point to grow from")
    return out


def scale_citations() -> pd.DataFrame:
    return pd.DataFrame(SCALE_CITATIONS)


def run() -> dict[str, pd.DataFrame]:
    comparison = market_size_comparison()
    write_parquet(comparison, OUT_COMPARISON, Provenance(
        parser="src.macro.analysis_scale.market_size_comparison", source_urls=[],
        notes="CLO row is a dated (Dec 2018) TO-VERIFY citation from Section 4; all others are current FRED-mirrored series.",
    ))

    growth = growth_10y()
    write_parquet(growth, OUT_GROWTH, Provenance(parser="src.macro.analysis_scale.growth_10y", source_urls=[]))

    citations = scale_citations()
    write_parquet(citations, OUT_CITATIONS, Provenance(
        parser="src.macro.analysis_scale.scale_citations", source_urls=[],
        notes="TO-VERIFY citations transcribed from Fed Financial Stability Report text already cached by Section 6.",
    ))

    logger.info("comparison=%d markets, growth=%d markets, citations=%d", len(comparison), len(growth), len(citations))
    return {"comparison": comparison, "growth": growth, "citations": citations}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
