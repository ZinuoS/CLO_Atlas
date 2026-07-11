"""Outstanding-stock comparators for the scale exhibit (slide 2): corporate &
foreign bonds, Treasury debt, munis, agency MBS — all FRED-mirrored Fed/
Treasury series, latest values current.

CLO outstanding has no dedicated Z.1/FRED series (config.FED_CLO_HOLDER_CITATION
already documents why — the Fed's EFA project has no CLO-specific page, and
the Z.1 "Issuers of ABS" sector aggregates all ABS issuers, CLOs included but
not isolated). Rather than fabricate a current CLO total, analysis_scale.py
reuses that Section 4 citation (a dated, TO-VERIFY Dec-2018 Fed FEDS-note
estimate of CLO securities held by U.S. investors) for the CLO bar, labeled
by its own as-of date rather than blended with the other series' current
values.

SIFMA's own statistics pages (the obvious first choice for this comparison)
were re-checked 2026-07-11 and remain gated — see docs/excluded_sources.md.
"""
from __future__ import annotations

import datetime as dt
import io
import logging

import pandas as pd

import config
from src.common.cache import Provenance, write_parquet
from src.common.http import CachedSession

logger = logging.getLogger("clo_atlas.macro.scrape_market_size")

OUT_PATH = config.INTERIM_DIR / "macro_market_size_series.parquet"


def scrape_market_size_series(session: CachedSession, series: dict[str, str] | None = None) -> pd.DataFrame:
    series = series or config.MACRO_MARKET_SIZE_FRED
    frames = []
    for label, series_id in series.items():
        result = session.get("https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": series_id})
        if result.status != 200:
            logger.warning("market-size series %s (%s) failed: status %d", label, series_id, result.status)
            continue
        df = pd.read_csv(io.BytesIO(result.content))
        df.columns = ["date", "value"]
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df["series"] = label
        df["series_id"] = series_id
        frames.append(df)
        logger.info("market-size %s (%s): %d observations", label, series_id, len(df))
    if not frames:
        raise RuntimeError("market-size scrape returned nothing for any series")
    return pd.concat(frames, ignore_index=True)


def run() -> pd.DataFrame:
    session = CachedSession()
    df = scrape_market_size_series(session)
    write_parquet(df, OUT_PATH, Provenance(
        source_urls=[f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}" for sid in config.MACRO_MARKET_SIZE_FRED.values()],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.macro.scrape_market_size",
    ))
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
