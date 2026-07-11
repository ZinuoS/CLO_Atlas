"""Litigation intensity for the LME/creditor-conflict era (Part C). The
originally planned join against presale LME vocabulary and realized rating
downgrade actions is NOT possible: Section 5's presale corpus and rating-
action data are both empty (S&P Akamai-walled, Fitch client-rendered — see
docs/excluded_sources.md and src/ratings/*). This reports litigation
intensity alone, with the missing links stated as gaps, not silently
dropped.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.future.analysis_legal_regime")

LITIGATION_PATH = config.INTERIM_DIR / "future_litigation.parquet"

OUT_INTENSITY = config.FINAL_DIR / "legal_regime_litigation_intensity.parquet"
OUT_CHAIN_STATUS = config.FINAL_DIR / "legal_regime_chain_status.parquet"


def litigation_intensity() -> pd.DataFrame:
    if not LITIGATION_PATH.exists():
        return pd.DataFrame(columns=["year", "query", "n_dockets"])
    df = read_parquet(LITIGATION_PATH).dropna(subset=["date_filed"])
    if df.empty:
        return pd.DataFrame(columns=["year", "query", "n_dockets"])
    df["year"] = pd.to_datetime(df["date_filed"]).dt.year
    return df.groupby(["year", "query"]).size().reset_index(name="n_dockets")


def chain_status() -> pd.DataFrame:
    return pd.DataFrame([
        {"link": "Litigation intensity", "status": "measured", "detail": "CourtListener docket counts by year (first page per query, not exhaustive)"},
        {"link": "-> LME vocabulary in presales/ratings", "status": "GAP", "detail": "Section 5 presale corpus is empty (S&P Akamai-walled, Fitch client-rendered)"},
        {"link": "-> realized downgrade actions", "status": "GAP", "detail": "ratings_transitions_monthly.parquet is empty for the same reason"},
    ])


def run() -> dict[str, pd.DataFrame]:
    intensity = litigation_intensity()
    write_parquet(intensity, OUT_INTENSITY, Provenance(parser="src.future.analysis_legal_regime.litigation_intensity", source_urls=[]))

    status = chain_status()
    write_parquet(status, OUT_CHAIN_STATUS, Provenance(parser="src.future.analysis_legal_regime.chain_status", source_urls=[]))

    logger.info("litigation_intensity=%d year-query rows, chain_status=%d links", len(intensity), len(status))
    return {"intensity": intensity, "chain_status": status}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
