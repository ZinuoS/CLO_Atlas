"""Federal Reserve Z.1 Financial Accounts of the United States — nonfinancial
corporate business debt: loans vs. bonds mix, and the bank vs. nonbank
lenders split (slide 2: "Banks stepped back. A trillion-dollar market
stepped in.").

The Z.1 Data Download Program's own package picker (Choose.aspx?rel=Z1)
serves only opaque hash-keyed "preformatted package" values
(`series=992060851bc881aa528002a0881075df` etc.) with no server-rendered
mnemonic-to-hash mapping — investigated directly 2026-07-11, not a guess.
FRED mirrors the identical Board-published Z.1 series under stable
`BOGZ1<mnemonic>` IDs (confirmed via each series' own FRED page title, not
assumed from the ID alone), so this scraper pulls from fredgraph.csv like
every other FRED-sourced module, and docs/sources.md records both the FRED
ID and the underlying Z.1 series code for each.

  BCNSDODNS   <-> Z.1 FL104104005.Q  Nonfinancial Corporate Business;
                                      Debt Securities and Loans; Liability, Level
  NCBDBIQ027S <-> Z.1 FL104122005.Q  Nonfinancial Corporate Business;
                                      Debt Securities; Liability, Level
  BLNECLBSNNCB<-> Z.1 FL103168005.Q  Nonfinancial Corporate Business;
                                      Depository Institution Loans N.e.c.; Liability, Level

Loans (all lenders) = total credit market debt - debt securities; the bank
share of those loans is BLNECLBSNNCB / loans, so nonbank share = 1 - that
ratio. Quarterly, back to 1945:Q4.
"""
from __future__ import annotations

import datetime as dt
import io
import logging

import pandas as pd

import config
from src.common.cache import Provenance, write_parquet
from src.common.http import CachedSession

logger = logging.getLogger("clo_atlas.macro.scrape_z1")

OUT_PATH = config.INTERIM_DIR / "macro_z1_series.parquet"


def scrape_z1_series(session: CachedSession, series: dict[str, str] | None = None) -> pd.DataFrame:
    series = series or config.MACRO_Z1_SERIES
    frames = []
    for label, series_id in series.items():
        result = session.get("https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": series_id})
        if result.status != 200:
            logger.warning("Z.1/FRED series %s (%s) failed: status %d", label, series_id, result.status)
            continue
        df = pd.read_csv(io.BytesIO(result.content))
        df.columns = ["date", "value"]
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df["series"] = label
        df["series_id"] = series_id
        frames.append(df)
        logger.info("Z.1/FRED %s (%s): %d observations", label, series_id, len(df))
    if not frames:
        raise RuntimeError("Z.1 scrape returned nothing for any series")
    return pd.concat(frames, ignore_index=True)


def run() -> pd.DataFrame:
    session = CachedSession()
    df = scrape_z1_series(session)
    write_parquet(df, OUT_PATH, Provenance(
        source_urls=[f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}" for sid in config.MACRO_Z1_SERIES.values()],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.macro.scrape_z1",
        notes="FRED's direct mirror of Board-published Z.1 Financial Accounts series (BOGZ1 mnemonic family), "
              "not the raw DDP CSV package picker — see module docstring.",
    ))
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
