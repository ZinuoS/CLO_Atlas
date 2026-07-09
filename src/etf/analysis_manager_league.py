"""CLO manager league table from ETF holdings (Section 1): who the ETF
complex actually buys, concentration (HHI), and cross-fund overlap (Jaccard).

Manager identity is extracted from each position's free-text deal description
(`deal_name_raw`, e.g. "KKR CLO 35  AR 4.88%..." -> "KKR") and then run
through common/entity.py's resolution cascade so "KKR", "KKR Financial",
etc. collapse to one canonical manager — this is exactly the cross-source
canonicalization entity.py exists for, used here within a single source
because even one issuer's free-text names aren't internally consistent.
"""
from __future__ import annotations

import logging
import re

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet
from src.common.entity import EntityResolver

logger = logging.getLogger("clo_atlas.etf.analysis_manager_league")

HOLDINGS_PATH = config.INTERIM_DIR / "etf_holdings.parquet"

OUT_LEAGUE = config.FINAL_DIR / "etf_manager_league.parquet"
OUT_HHI = config.FINAL_DIR / "etf_manager_hhi.parquet"
OUT_OVERLAP = config.FINAL_DIR / "etf_fund_overlap_jaccard.parquet"

_CLO_SPLIT = re.compile(r"\bCLO\b", re.IGNORECASE)
_TRAILING_NOISE = re.compile(r"[\d|].*$")


def extract_manager_name(deal_name_raw: str, manager_raw_fallback: str | None) -> str:
    if not isinstance(deal_name_raw, str) or not deal_name_raw.strip():
        return manager_raw_fallback or "Unknown"
    parts = _CLO_SPLIT.split(deal_name_raw, maxsplit=1)
    candidate = parts[0].strip() if len(parts) > 1 else deal_name_raw
    candidate = _TRAILING_NOISE.sub("", candidate).strip(" ,.-")
    return candidate if candidate else (manager_raw_fallback or "Unknown")


def manager_league(holdings: pd.DataFrame) -> pd.DataFrame:
    if holdings.empty:
        return pd.DataFrame(columns=["date", "canonical_manager", "total_par", "n_positions", "n_funds"])

    holdings = holdings.copy()
    holdings["manager_name_guess"] = holdings.apply(
        lambda r: extract_manager_name(r["deal_name_raw"], r["manager_raw"]), axis=1)

    resolver = EntityResolver()
    resolver.bootstrap(holdings["manager_name_guess"].dropna().unique().tolist())
    resolved = resolver.resolve_many(holdings["manager_name_guess"].tolist(), source="etf_holdings")
    holdings["canonical_manager"] = resolved["canonical_name"].values
    resolver.save()

    league = holdings.groupby(["date", "canonical_manager"]).agg(
        total_par=("par", "sum"), n_positions=("cusip", "count"), n_funds=("fund", "nunique")
    ).reset_index()
    return league.sort_values(["date", "total_par"], ascending=[True, False]).reset_index(drop=True)


def manager_hhi(league: pd.DataFrame) -> pd.DataFrame:
    if league.empty:
        return pd.DataFrame(columns=["date", "hhi", "top5_share"])
    rows = []
    for date, grp in league.groupby("date"):
        shares = grp["total_par"] / grp["total_par"].sum()
        hhi = (shares ** 2).sum() * 10_000  # standard HHI scale (0-10,000)
        top5_share = shares.sort_values(ascending=False).head(5).sum()
        rows.append({"date": date, "hhi": hhi, "top5_share": top5_share})
    return pd.DataFrame(rows)


def fund_overlap_jaccard(holdings: pd.DataFrame) -> pd.DataFrame:
    """Jaccard similarity of deal sets (by CUSIP prefix / deal_name_raw) between
    every pair of funds on the most recent common date."""
    if holdings.empty or holdings["fund"].nunique() < 2:
        return pd.DataFrame(columns=["date", "fund_a", "fund_b", "jaccard"])
    latest_date = holdings["date"].max()
    snapshot = holdings[holdings["date"] == latest_date]
    funds = sorted(snapshot["fund"].unique())
    rows = []
    for i, fa in enumerate(funds):
        set_a = set(snapshot.loc[snapshot["fund"] == fa, "cusip"])
        for fb in funds[i + 1:]:
            set_b = set(snapshot.loc[snapshot["fund"] == fb, "cusip"])
            union = set_a | set_b
            jaccard = len(set_a & set_b) / len(union) if union else 0.0
            rows.append({"date": latest_date, "fund_a": fa, "fund_b": fb, "jaccard": jaccard})
    return pd.DataFrame(rows)


def run() -> dict[str, pd.DataFrame]:
    holdings = read_parquet(HOLDINGS_PATH) if HOLDINGS_PATH.exists() else pd.DataFrame()

    league = manager_league(holdings)
    write_parquet(league, OUT_LEAGUE, Provenance(parser="src.etf.analysis_manager_league.manager_league", source_urls=[]))

    hhi = manager_hhi(league)
    write_parquet(hhi, OUT_HHI, Provenance(parser="src.etf.analysis_manager_league.manager_hhi", source_urls=[]))

    overlap = fund_overlap_jaccard(holdings)
    write_parquet(overlap, OUT_OVERLAP, Provenance(parser="src.etf.analysis_manager_league.fund_overlap_jaccard", source_urls=[]))

    logger.info("manager_league=%d rows, hhi=%d dates, overlap=%d fund-pairs", len(league), len(hhi), len(overlap))
    return {"league": league, "hhi": hhi, "overlap": overlap}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
