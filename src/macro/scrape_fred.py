"""Macro opener FRED pull (slides 1-2): policy & curve, credit spreads, SLOOS
bank-tightening series, lending stock, inflation/real economy, recession
shading. Same fredgraph.csv, no-key-needed pattern as src/official/scrape_fred.py
and src/etf/scrape_nav_flows.py, but this module owns its own (larger) series
list — config.MACRO_FRED_SERIES — rather than re-pulling those modules' output.
"""
from __future__ import annotations

import datetime as dt
import io
import logging

import pandas as pd

import config
from src.common.cache import Provenance, write_parquet
from src.common.http import CachedSession

logger = logging.getLogger("clo_atlas.macro.scrape_fred")

OUT_PATH = config.INTERIM_DIR / "macro_fred_series.parquet"


def scrape_fred_series(session: CachedSession, series: dict[str, str] | None = None) -> pd.DataFrame:
    series = series or config.MACRO_FRED_SERIES
    frames = []
    for label, series_id in series.items():
        result = session.get("https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": series_id})
        if result.status != 200:
            logger.warning("FRED series %s (%s) failed: status %d", label, series_id, result.status)
            continue
        df = pd.read_csv(io.BytesIO(result.content))
        df.columns = ["date", "value"]
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df["series"] = label
        df["series_id"] = series_id
        frames.append(df)
        logger.info("FRED %s (%s): %d observations", label, series_id, len(df))
    if not frames:
        raise RuntimeError("FRED scrape returned nothing for any macro series")
    return pd.concat(frames, ignore_index=True)


def run() -> pd.DataFrame:
    session = CachedSession()
    df = scrape_fred_series(session)
    write_parquet(df, OUT_PATH, Provenance(
        source_urls=[f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}" for sid in config.MACRO_FRED_SERIES.values()],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.macro.scrape_fred",
    ))
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
