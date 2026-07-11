"""Portfolio style from position-level CLO equity holdings (Section 2
deep-dive): shelf/manager concentration, vintage mix, position sizing.

Manager identity is NOT independently verified here — CLO deal names
overwhelmingly encode their manager's shelf name (e.g. "Dryden 53 CLO" is
PGIM's shelf, "Octagon Investment Partners 27" is Octagon Credit
Investors'), so the deal-name prefix (stripped of its trailing roman-
numeral/series suffix) is used as a `shelf_name` proxy for repeat-manager
relationships. This is NOT a verified manager-entity mapping (that would
need its own curated lookup table, out of scope this pass) — it is labeled
`shelf_name` throughout, not `manager`, and flagged as a proxy on every
chart it feeds.

Primary-vs-secondary acquisition timing (a position appearing within N
quarters of a deal's close = primary proxy) needs each CLO's actual closing
date, which NPORT-P doesn't carry — also not attempted; logged as a gap.
"""
from __future__ import annotations

import logging
import re

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.cef.analysis_portfolio_style")

POSITIONS_PATH = config.INTERIM_DIR / "cef_clo_positions.parquet"

OUT_SHELF_CONCENTRATION = config.FINAL_DIR / "portfolio_shelf_concentration.parquet"
OUT_VINTAGE_MIX = config.FINAL_DIR / "portfolio_vintage_mix.parquet"
OUT_POSITION_SIZING = config.FINAL_DIR / "portfolio_position_sizing.parquet"

_SHELF_SUFFIX_PATTERN = re.compile(
    r",?\s*(CLO)?\s*(\d{4}-)?\s*[\dIVXLC]*[\-\s]?R{0,2}\s*,?\s*(Ltd\.?|LLC|Limited|Inc\.?)?\s*$", re.IGNORECASE
)


def _shelf_name(deal_name: str) -> str:
    """Strip trailing series number/refi marker/entity suffix to get the
    repeat-manager shelf name, e.g. 'Octagon Investment Partners 27, Ltd.'
    -> 'Octagon Investment Partners'."""
    name = _SHELF_SUFFIX_PATTERN.sub("", deal_name).strip()
    return name if name else deal_name


def _load_positions() -> pd.DataFrame:
    if not POSITIONS_PATH.exists():
        return pd.DataFrame()
    df = read_parquet(POSITIONS_PATH)
    return df[df["is_clo"] == True].copy()  # noqa: E712


def shelf_concentration() -> pd.DataFrame:
    df = _load_positions()
    if df.empty:
        logger.warning("no CLO position data cached; shelf_concentration is empty")
        return pd.DataFrame(columns=["fund", "shelf_name", "n_positions", "total_valUSD", "share_of_fund"])
    df["shelf_name"] = df["name"].apply(_shelf_name)
    by_shelf = df.groupby(["fund", "shelf_name"]).agg(
        n_positions=("cusip", "nunique"), total_valUSD=("valUSD", "sum")
    ).reset_index()
    fund_totals = by_shelf.groupby("fund")["total_valUSD"].transform("sum")
    by_shelf["share_of_fund"] = by_shelf["total_valUSD"] / fund_totals
    return by_shelf.sort_values(["fund", "total_valUSD"], ascending=[True, False])


def vintage_mix() -> pd.DataFrame:
    """Vintage proxied by maturity year bucketed into 5y bands (NPORT
    doesn't carry the deal's original closing date, only tranche maturity —
    a longer-dated maturity roughly correlates with a more recent vintage,
    but this is a proxy, not the closing date itself)."""
    df = _load_positions()
    if df.empty or "maturityDt" not in df.columns:
        return pd.DataFrame(columns=["fund", "maturity_band", "total_valUSD", "share_of_fund"])
    df = df.dropna(subset=["maturityDt"]).copy()
    df["maturity_year"] = pd.to_datetime(df["maturityDt"], errors="coerce").dt.year
    df = df.dropna(subset=["maturity_year"])
    df["maturity_band"] = (df["maturity_year"] // 5 * 5).astype(int).astype(str) + "-" + \
                           (df["maturity_year"] // 5 * 5 + 4).astype(int).astype(str)
    by_band = df.groupby(["fund", "maturity_band"]).agg(total_valUSD=("valUSD", "sum")).reset_index()
    fund_totals = by_band.groupby("fund")["total_valUSD"].transform("sum")
    by_band["share_of_fund"] = by_band["total_valUSD"] / fund_totals
    return by_band.sort_values(["fund", "maturity_band"])


def position_sizing() -> pd.DataFrame:
    df = _load_positions()
    if df.empty:
        return pd.DataFrame(columns=["fund", "pctVal", "annualizedRt"])
    return df[["fund", "period", "pctVal", "annualizedRt"]].dropna(subset=["pctVal"])


def run() -> dict[str, pd.DataFrame]:
    shelf = shelf_concentration()
    write_parquet(shelf, OUT_SHELF_CONCENTRATION, Provenance(
        parser="src.cef.analysis_portfolio_style.shelf_concentration", source_urls=[],
        notes="shelf_name is a deal-name-prefix proxy for manager identity, not a verified manager mapping.",
    ))

    vintage = vintage_mix()
    write_parquet(vintage, OUT_VINTAGE_MIX, Provenance(
        parser="src.cef.analysis_portfolio_style.vintage_mix", source_urls=[],
        notes="Bucketed by tranche maturity year, a proxy for deal vintage — NPORT-P doesn't carry each deal's closing date.",
    ))

    sizing = position_sizing()
    write_parquet(sizing, OUT_POSITION_SIZING, Provenance(parser="src.cef.analysis_portfolio_style.position_sizing", source_urls=[]))

    logger.info("shelf_concentration=%d rows, vintage_mix=%d rows, position_sizing=%d rows",
                len(shelf), len(vintage), len(sizing))
    return {"shelf_concentration": shelf, "vintage_mix": vintage, "position_sizing": sizing}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
