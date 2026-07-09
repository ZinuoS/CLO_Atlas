"""Upgrade/downgrade transitions and the senior-tranche impairment record
(Section 5) — degrades gracefully to empty.

Depends on scrape_actions.py, which is stubbed (S&P Akamai-blocked, Fitch
client-rendered with no free API — see that module's docstring and
docs/excluded_sources.md). Kept as a real module with the documented
interface every analysis layer shares; wiring a future data source (a
licensed data vendor, or a third party with a clear scraping license) only
means filling in scrape_actions.run().
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, write_parquet
from src.ratings import scrape_actions

logger = logging.getLogger("clo_atlas.ratings.analysis_transitions")

OUT_MONTHLY = config.FINAL_DIR / "ratings_transitions_monthly.parquet"
OUT_IMPAIRMENTS = config.FINAL_DIR / "ratings_senior_impairments.parquet"


def transitions_monthly() -> pd.DataFrame:
    raw = scrape_actions.run()
    if raw.empty:
        logger.warning("no rating-action data available; transitions_monthly is empty")
        return pd.DataFrame(columns=["month", "agency", "upgrades", "downgrades", "affirms"])
    return raw


def senior_impairments() -> pd.DataFrame:
    raw = scrape_actions.run()
    if raw.empty:
        logger.warning("no rating-action data available; senior_impairments is empty")
        return pd.DataFrame(columns=["date", "deal", "tranche", "original_rating", "impaired"])
    return raw


def run() -> dict[str, pd.DataFrame]:
    monthly = transitions_monthly()
    write_parquet(monthly, OUT_MONTHLY, Provenance(parser="src.ratings.analysis_transitions.transitions_monthly", source_urls=[]))

    impairments = senior_impairments()
    write_parquet(impairments, OUT_IMPAIRMENTS, Provenance(parser="src.ratings.analysis_transitions.senior_impairments", source_urls=[]))

    return {"monthly": monthly, "impairments": impairments}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
