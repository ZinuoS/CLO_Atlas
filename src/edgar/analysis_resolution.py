"""Issuer entity resolution across every Section 3 source (Section 3): BDC
SOI company names and bank-loan-fund NPORT-P names. The resolution pipeline's
own performance is itself an exhibit here — the match-cascade funnel
(exact / alias / fuzzy / unresolved) feeds viz_funnel.py, a methods slide
that doubles as an engineering flex per the mission brief.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet
from src.common.entity import EntityResolver

logger = logging.getLogger("clo_atlas.edgar.analysis_resolution")

BDC_SOI_PATH = config.INTERIM_DIR / "bdc_soi_positions.parquet"
BANK_LOAN_PATH = config.INTERIM_DIR / "bank_loan_fund_positions.parquet"

OUT_RESOLVED = config.FINAL_DIR / "edgar_resolved_issuers.parquet"
OUT_FUNNEL = config.FINAL_DIR / "edgar_resolution_funnel.parquet"
OUT_REVIEW = config.FINAL_DIR / "edgar_resolution_review_queue.parquet"


def _collect_raw_names() -> pd.DataFrame:
    rows = []
    if BDC_SOI_PATH.exists():
        soi = read_parquet(BDC_SOI_PATH)
        for _, r in soi[["company", "fund", "period"]].drop_duplicates().iterrows():
            rows.append({"raw_name": r["company"], "source": "bdc_soi", "filer": r["fund"], "period": r["period"]})
    if BANK_LOAN_PATH.exists():
        nport = read_parquet(BANK_LOAN_PATH)
        for _, r in nport[["name", "fund", "period"]].drop_duplicates().iterrows():
            rows.append({"raw_name": r["name"], "source": "bank_loan_nport", "filer": r["fund"], "period": r["period"]})
    return pd.DataFrame(rows)


def resolve_all_issuers() -> tuple[pd.DataFrame, dict]:
    raw = _collect_raw_names()
    if raw.empty:
        logger.warning("no BDC SOI or bank-loan NPORT data cached; resolve_all_issuers is empty")
        return pd.DataFrame(), {}

    resolver = EntityResolver(
        canonical_path=config.INTERIM_DIR / "edgar_entity_canonical.parquet",
        alias_path=config.INTERIM_DIR / "edgar_entity_aliases.parquet",
    )
    # Bootstrap the canonical table from BDC SOI names only (the larger,
    # more authoritative source), then resolve the bank-loan-fund NPORT
    # names AGAINST that set. This is what actually exercises the match
    # cascade for genuine cross-source consolidation — bootstrapping from
    # the full combined name list first would make every name trivially
    # "exact" match itself and never touch the fuzzy tiers.
    bdc_names = raw.loc[raw["source"] == "bdc_soi", "raw_name"].dropna().unique().tolist()
    resolver.bootstrap(bdc_names)

    # Resolving BDC names again after they're already the canonical set is
    # cheap (every one is an exact self-match) and keeps the output schema
    # uniform across both sources.
    resolved = resolver.resolve_many(raw["raw_name"].tolist(), source="edgar_issuers")
    resolver.save()

    merged = pd.concat([raw.reset_index(drop=True), resolved[["canonical_id", "canonical_name", "method", "score"]]], axis=1)
    funnel = resolver.match_funnel_stats(resolved)
    logger.info("entity resolution funnel: %s", funnel)
    return merged, funnel


def run() -> dict[str, pd.DataFrame]:
    resolved, funnel = resolve_all_issuers()
    write_parquet(resolved, OUT_RESOLVED, Provenance(parser="src.edgar.analysis_resolution.resolve_all_issuers", source_urls=[]))

    funnel_df = pd.DataFrame([funnel]) if funnel else pd.DataFrame(
        columns=["total", "exact", "alias", "fuzzy_auto", "fuzzy_review", "unresolved", "match_rate"])
    write_parquet(funnel_df, OUT_FUNNEL, Provenance(parser="src.edgar.analysis_resolution.resolve_all_issuers", source_urls=[]))

    review_path = config.INTERIM_DIR / "entity_review_queue.csv"
    review_df = pd.read_csv(review_path) if review_path.exists() else pd.DataFrame()
    write_parquet(review_df, OUT_REVIEW, Provenance(parser="src.edgar.analysis_resolution.resolve_all_issuers", source_urls=[]))

    return {"resolved": resolved, "funnel": funnel_df, "review_queue": review_df}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
