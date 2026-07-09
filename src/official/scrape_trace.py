"""FINRA/ICE Data Services structured-product pricing table, CBO-CDO-CLO
sheet (Section 4): the closest free, public proxy for TRACE-based CLO
tranche pricing and liquidity conditions.

Verified 2026-07-09: a direct, unauthenticated binary download, no login. The
workbook is a same-day snapshot republished at a fixed URL each day, not a
historical archive, so (like the ETF NAV snapshots in Section 1) a real time
series accretes only from whenever this project starts scraping it daily.
"""
from __future__ import annotations

import datetime as dt
import io
import logging

import pandas as pd

import config
from src.common.cache import Provenance, write_parquet
from src.common.http import CachedSession

logger = logging.getLogger("clo_atlas.official.scrape_trace")

OUT_PATH = config.INTERIM_DIR / "trace_clo_pricing.parquet"


def parse_pxtables_clo_sheet(xlsx_bytes: bytes) -> pd.DataFrame:
    """The CBO-CDO-CLO sheet is a small pivoted metric-by-band table:
    rows are metrics (average price, weighted avg price, quartiles, ...),
    columns are (rating band x vintage) pairs. Reshape to tidy: one row per
    (metric, rating_band, vintage, value).
    """
    raw = pd.read_excel(io.BytesIO(xlsx_bytes), sheet_name=config.FINRA_PXTABLES_CLO_SHEET, header=None)

    as_of = None
    for _, row in raw.iterrows():
        for cell in row:
            if isinstance(cell, str) and "DATA AS OF" in cell.upper():
                idx = list(row).index(cell)
                as_of_val = row.iloc[idx + 1] if idx + 1 < len(row) else None
                as_of = pd.to_datetime(as_of_val).date() if pd.notna(as_of_val) else None
    as_of = as_of or dt.date.today()

    header_row_idx = None
    for i, row in raw.iterrows():
        if any(isinstance(c, str) and "AAA" in str(c) for c in row):
            header_row_idx = i
            break
    if header_row_idx is None:
        raise ValueError("could not locate the rating-band header row in CBO-CDO-CLO sheet")

    band_row = raw.iloc[header_row_idx].tolist()
    vintage_row = raw.iloc[header_row_idx + 1].tolist()
    bands = []
    current_band = None
    for cell in band_row:
        if isinstance(cell, str) and cell.strip():
            current_band = cell.strip()
        bands.append(current_band)

    # The sheet stacks three blocks under the same rating-band/vintage column
    # headers: per-trade PRICE stats, then a "VOLUME OF TRADES ($000s)" block
    # (whose sub-rows are $ volume by counterparty/size), then a "NUMBER OF
    # TRADES" block with the *same* sub-row labels (CUSTOMER BUY, <= $1MM, ...)
    # but as trade counts, not dollars. Track which block we're in so
    # "CUSTOMER BUY" the dollar figure and "CUSTOMER BUY" the trade count
    # don't collide under one (metric, rating_band, vintage) key.
    _BLOCK_HEADERS = {
        "VOLUME OF TRADES (000'S)": "volume_usd_000s",
        "NUMBER OF TRADES": "trade_count",
    }
    records = []
    block = "price_stat"
    for i in range(header_row_idx + 2, len(raw)):
        row = raw.iloc[i].tolist()
        metric = row[1] if len(row) > 1 else None
        if not isinstance(metric, str) or not metric.strip():
            continue
        metric = metric.strip()
        block = _BLOCK_HEADERS.get(metric, block)
        for col_idx in range(2, len(row)):
            band = bands[col_idx] if col_idx < len(bands) else None
            vintage = vintage_row[col_idx] if col_idx < len(vintage_row) else None
            value = row[col_idx]
            if band is None or not isinstance(vintage, str) or pd.isna(value):
                continue
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
            records.append({
                "date": as_of, "block": block, "metric": metric, "rating_band": band,
                "vintage": vintage.strip(), "value": value,
            })

    if not records:
        raise ValueError("parsed zero rows from CBO-CDO-CLO sheet")
    return pd.DataFrame.from_records(records)


def run() -> pd.DataFrame:
    session = CachedSession()
    result = session.get(config.FINRA_PXTABLES_URL)
    if result.status != 200:
        raise RuntimeError(f"FINRA PXTABLES download failed: status {result.status}")

    new_data = parse_pxtables_clo_sheet(result.content)
    logger.info("parsed %d CLO pricing rows as of %s", len(new_data), new_data["date"].iloc[0])

    if OUT_PATH.exists():
        existing = pd.read_parquet(OUT_PATH)
        combined = pd.concat([existing, new_data], ignore_index=True) if len(existing) else new_data
        combined = combined.drop_duplicates(subset=["date", "block", "metric", "rating_band", "vintage"], keep="last")
    else:
        combined = new_data

    write_parquet(combined, OUT_PATH, Provenance(
        source_urls=[config.FINRA_PXTABLES_URL],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.official.scrape_trace",
        notes="Same-day snapshot; history accretes from repeated runs.",
    ))
    logger.info("wrote %d total CLO pricing rows (%d new) to %s", len(combined), len(new_data), OUT_PATH)
    return combined


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
