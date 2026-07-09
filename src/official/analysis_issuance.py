"""CLO issuance cycle decomposition (Section 4) — degrades gracefully to
empty. Depends on scrape_sifma.py, which is stubbed (gated behind a lead-gen
form — see that module's docstring and docs/excluded_sources.md). Kept as a
real module with the documented interface analysis layers share; wiring a
future SIFMA integration only means filling in scrape_sifma.run().
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, write_parquet
from src.official import scrape_sifma

logger = logging.getLogger("clo_atlas.official.analysis_issuance")

OUT_PATH = config.FINAL_DIR / "clo_issuance_cycle.parquet"


def issuance_cycle() -> pd.DataFrame:
    raw = scrape_sifma.run()
    if raw.empty:
        logger.warning("no SIFMA issuance data available; issuance_cycle is empty (see scrape_sifma.py docstring)")
        return pd.DataFrame(columns=["period", "new_issue_usd", "refi_usd", "reset_usd", "effr"])
    return raw


def run() -> pd.DataFrame:
    df = issuance_cycle()
    write_parquet(df, OUT_PATH, Provenance(parser="src.official.analysis_issuance.issuance_cycle", source_urls=[]))
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
