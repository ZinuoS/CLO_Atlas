"""Registered product pipeline (Part C): CLO-accessible product
registrations per year by wrapper type, and sponsor entry order — the
institutionalization-of-retail-access curve.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.future.analysis_pipeline")

PIPELINE_PATH = config.INTERIM_DIR / "future_product_pipeline.parquet"

OUT_BY_YEAR = config.FINAL_DIR / "pipeline_registrations_by_year.parquet"
OUT_SPONSOR_ORDER = config.FINAL_DIR / "pipeline_sponsor_entry_order.parquet"

_WRAPPER_LABELS = {"N-2": "Closed-end/interval fund", "485APOS": "Open-end fund (ETF/mutual)", "N-1A": "Open-end fund (ETF/mutual)"}


def _wrapper_type(form: str) -> str:
    base = (form or "").split("/")[0]
    return _WRAPPER_LABELS.get(base, base)


def registrations_by_year() -> pd.DataFrame:
    if not PIPELINE_PATH.exists():
        return pd.DataFrame(columns=["year", "wrapper_type", "n_filings"])
    df = read_parquet(PIPELINE_PATH)
    if df.empty:
        return pd.DataFrame(columns=["year", "wrapper_type", "n_filings"])
    df["year"] = pd.to_datetime(df["file_date"]).dt.year
    df["wrapper_type"] = df["form"].apply(_wrapper_type)
    return df.groupby(["year", "wrapper_type"]).size().reset_index(name="n_filings")


def sponsor_entry_order() -> pd.DataFrame:
    """First observed filing date per distinct filer — who came to the
    party, in order."""
    if not PIPELINE_PATH.exists():
        return pd.DataFrame(columns=["filer", "first_filing_date", "n_filings"])
    df = read_parquet(PIPELINE_PATH)
    if df.empty:
        return pd.DataFrame(columns=["filer", "first_filing_date", "n_filings"])
    df["file_date"] = pd.to_datetime(df["file_date"])
    out = df.groupby("filer").agg(first_filing_date=("file_date", "min"), n_filings=("file_date", "count")).reset_index()
    return out.sort_values("first_filing_date")


def run() -> dict[str, pd.DataFrame]:
    by_year = registrations_by_year()
    write_parquet(by_year, OUT_BY_YEAR, Provenance(parser="src.future.analysis_pipeline.registrations_by_year", source_urls=[]))

    sponsor_order = sponsor_entry_order()
    write_parquet(sponsor_order, OUT_SPONSOR_ORDER, Provenance(
        parser="src.future.analysis_pipeline.sponsor_entry_order", source_urls=[],
        notes="First filing date is bounded by EDGAR full-text search's ~30-filings-per-form sample, not exhaustive.",
    ))

    logger.info("registrations_by_year=%d rows, sponsor_entry_order=%d sponsors", len(by_year), len(sponsor_order))
    return {"by_year": by_year, "sponsor_order": sponsor_order}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
