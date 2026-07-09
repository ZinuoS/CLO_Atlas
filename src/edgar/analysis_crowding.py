"""Crowding: most widely held issuers, industry concentration, and BDC
portfolio overlap (Section 3). Built from the entity-resolved issuer table.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.edgar.analysis_crowding")

RESOLVED_PATH = config.FINAL_DIR / "edgar_resolved_issuers.parquet"

OUT_TOP = config.FINAL_DIR / "edgar_crowded_issuers.parquet"
OUT_OVERLAP = config.FINAL_DIR / "edgar_bdc_overlap_jaccard.parquet"


def top_crowded_issuers(n: int = 25) -> pd.DataFrame:
    if not RESOLVED_PATH.exists():
        logger.warning("no resolved-issuer table cached; run analysis_resolution.py first")
        return pd.DataFrame(columns=["canonical_name", "n_filers", "n_positions"])
    resolved = read_parquet(RESOLVED_PATH)
    latest_period = resolved.groupby("source")["period"].transform("max")
    snap = resolved[resolved["period"] == latest_period]
    g = snap.groupby("canonical_name").agg(n_filers=("filer", "nunique"), n_positions=("raw_name", "count")).reset_index()
    return g.sort_values("n_filers", ascending=False).head(n)


def bdc_overlap_jaccard() -> pd.DataFrame:
    if not RESOLVED_PATH.exists():
        return pd.DataFrame(columns=["filer_a", "filer_b", "jaccard"])
    resolved = read_parquet(RESOLVED_PATH)
    bdc = resolved[resolved["source"] == "bdc_soi"]
    if bdc.empty:
        return pd.DataFrame(columns=["filer_a", "filer_b", "jaccard"])
    # Different BDCs report on different fiscal quarter-end dates, so the
    # single latest period isn't necessarily shared by more than one filer —
    # use whichever period the most distinct filers actually reported.
    best_period = bdc.groupby("period")["filer"].nunique().idxmax()
    latest = bdc[bdc["period"] == best_period]
    filers = sorted(latest["filer"].unique())
    if len(filers) < 2:
        logger.warning("only %d filer(s) share a common reporting period (%s); bdc_overlap_jaccard is empty",
                        len(filers), best_period)
        return pd.DataFrame(columns=["filer_a", "filer_b", "jaccard", "n_shared"])
    rows = []
    for i, fa in enumerate(filers):
        set_a = set(latest.loc[latest["filer"] == fa, "canonical_name"])
        for fb in filers[i + 1:]:
            set_b = set(latest.loc[latest["filer"] == fb, "canonical_name"])
            union = set_a | set_b
            jaccard = len(set_a & set_b) / len(union) if union else 0.0
            rows.append({"filer_a": fa, "filer_b": fb, "jaccard": jaccard, "n_shared": len(set_a & set_b)})
    return pd.DataFrame(rows).sort_values("jaccard", ascending=False)


def run() -> dict[str, pd.DataFrame]:
    top = top_crowded_issuers()
    write_parquet(top, OUT_TOP, Provenance(parser="src.edgar.analysis_crowding.top_crowded_issuers", source_urls=[]))

    overlap = bdc_overlap_jaccard()
    write_parquet(overlap, OUT_OVERLAP, Provenance(parser="src.edgar.analysis_crowding.bdc_overlap_jaccard", source_urls=[]))

    logger.info("top_crowded_issuers=%d rows, bdc_overlap=%d pairs", len(top), len(overlap))
    return {"top": top, "overlap": overlap}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
