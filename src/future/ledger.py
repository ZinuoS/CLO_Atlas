"""VERIFIED/TO-VERIFY ledger for the future-direction section (Part C)."""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import read_parquet

logger = logging.getLogger("clo_atlas.future.ledger")

LEDGER_OUT = config.FINAL_DIR / "future_ledger.parquet"


def _row(value, computation_or_citation, as_of, tag):
    return {"value": value, "computation_or_citation": computation_or_citation, "as_of": as_of, "tag": tag}


def build_ledger() -> pd.DataFrame:
    rows = []

    by_year_path = config.FINAL_DIR / "pipeline_registrations_by_year.parquet"
    if by_year_path.exists():
        by_year = read_parquet(by_year_path)
        if len(by_year):
            rows.append(_row(f"{by_year['n_filings'].sum()} CLO-mentioning fund-registration filings across {by_year['year'].nunique()} years",
                              "analysis_pipeline.registrations_by_year(), from EDGAR full-text search", "n/a", "VERIFIED"))

    sponsor_path = config.FINAL_DIR / "pipeline_sponsor_entry_order.parquet"
    if sponsor_path.exists():
        sponsors = read_parquet(sponsor_path)
        if len(sponsors):
            rows.append(_row(f"{len(sponsors)} distinct sponsors observed in the registration pipeline sample",
                              "analysis_pipeline.sponsor_entry_order()", "n/a", "VERIFIED"))

    mm_path = config.FINAL_DIR / "composition_shift_mm_trend.parquet"
    if mm_path.exists():
        mm = read_parquet(mm_path)
        rows.append(_row(f"MM-shelf share proxy: {len(mm)} fund-period observations (two funds' own holdings, not market-wide)",
                          "analysis_composition_shift.mm_share_trend() — Section 5 presale corpus unavailable, see module docstring",
                          "n/a", "VERIFIED" if len(mm) else "GAP — not plotted"))

    litigation_path = config.FINAL_DIR / "legal_regime_litigation_intensity.parquet"
    if litigation_path.exists():
        lit = read_parquet(litigation_path)
        if len(lit):
            rows.append(_row(f"{lit['n_dockets'].sum()} LME-era dockets found across {lit['query'].nunique()} query terms",
                              "analysis_legal_regime.litigation_intensity(), from CourtListener/RECAP", "n/a", "VERIFIED"))

    chain_path = config.FINAL_DIR / "legal_regime_chain_status.parquet"
    if chain_path.exists():
        chain = read_parquet(chain_path)
        for _, r in chain.iterrows():
            tag = "GAP — not plotted" if r["status"] == "GAP" else "VERIFIED"
            rows.append(_row(f"{r['link']}: {r['status']}", r["detail"], "n/a", tag))

    snapshot_path = config.FINAL_DIR / "maturation_scorecard_snapshot.parquet"
    if snapshot_path.exists():
        snap = read_parquet(snapshot_path)
        for _, r in snap.iterrows():
            rows.append(_row(f"{r['metric']}: {r['value']}", "analysis_maturation_scorecard.snapshot_table()", str(r["as_of"]), "VERIFIED"))

    options_path = config.INTERIM_DIR / "future_etf_options.parquet"
    if options_path.exists():
        options = read_parquet(options_path)
        n_with = options["has_listed_options"].sum()
        rows.append(_row(f"{n_with}/{len(options)} checked CLO ETFs have listed options",
                          "scrape_etf_filings_options.scrape_options()", "n/a", "VERIFIED"))

    watchlist_path = config.FINAL_DIR / "scenarios_watchlist.parquet"
    if watchlist_path.exists():
        wl = read_parquet(watchlist_path)
        rows.append(_row(f"{len(wl)}-row scenario-monitoring watchlist across {wl['scenario'].nunique()} scenarios",
                          "analysis_scenarios.scenario_watchlist() — a monitoring map, not a forecast", "n/a", "VERIFIED"))

    return pd.DataFrame(rows)


def run() -> pd.DataFrame:
    ledger = build_ledger()
    ledger.to_parquet(LEDGER_OUT, index=False)
    logger.info("wrote %d ledger rows to %s", len(ledger), LEDGER_OUT)
    return ledger


def main():
    logging.basicConfig(level=logging.INFO)
    print(run().to_string(index=False))


if __name__ == "__main__":
    main()
