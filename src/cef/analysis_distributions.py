"""Distribution history for CLO CEFs (Section 2): yield on price, yield on
book value, and cut/raise events — the "dividend-chaser" story. Fully
computable today; yfinance carries complete corporate-action history even
for these plain-equity-classified tickers.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.cef.analysis_distributions")

DIST_PATH = config.INTERIM_DIR / "cef_distributions.parquet"
PRICES_PATH = config.INTERIM_DIR / "cef_prices.parquet"
SNAPSHOTS_PATH = config.INTERIM_DIR / "cef_bookvalue_snapshots.parquet"

OUT_HISTORY = config.FINAL_DIR / "cef_distribution_history.parquet"
OUT_YIELD = config.FINAL_DIR / "cef_yield_on_price_and_book.parquet"
OUT_EVENTS = config.FINAL_DIR / "cef_distribution_change_events.parquet"


def distribution_history() -> pd.DataFrame:
    if not DIST_PATH.exists():
        logger.warning("no distribution history cached; run scrape_prices_nav.py first")
        return pd.DataFrame(columns=["ex_date", "ticker", "amount"])
    return read_parquet(DIST_PATH).sort_values(["ticker", "ex_date"])


def annualized_yield_on_price_and_book(dist: pd.DataFrame) -> pd.DataFrame:
    """Trailing-12-month distributions / current price, and / current book
    value (the NAV proxy). One row per fund, using the latest price/book snapshot."""
    if dist.empty or not PRICES_PATH.exists():
        return pd.DataFrame(columns=["ticker", "ttm_distributions", "price", "yield_on_price",
                                       "book_value_per_share", "yield_on_book"])
    prices = read_parquet(PRICES_PATH)
    cutoff = dist["ex_date"].max() - pd.Timedelta(days=365)
    ttm = dist[dist["ex_date"] >= cutoff].groupby("ticker")["amount"].sum().rename("ttm_distributions")

    latest_price = prices.sort_values("date").groupby("ticker")["close"].last().rename("price")
    out = pd.concat([ttm, latest_price], axis=1).dropna()
    out["yield_on_price"] = out["ttm_distributions"] / out["price"]

    if SNAPSHOTS_PATH.exists():
        book = read_parquet(SNAPSHOTS_PATH).dropna(subset=["book_value_per_share"])
        book = book.sort_values("date").groupby("ticker")["book_value_per_share"].last()
        out = out.join(book, how="left")
        out["yield_on_book"] = out["ttm_distributions"] / out["book_value_per_share"]
    else:
        out["book_value_per_share"] = None
        out["yield_on_book"] = None

    return out.reset_index().rename(columns={"index": "ticker"})


def distribution_change_events(dist: pd.DataFrame, threshold: float = 0.01) -> pd.DataFrame:
    """Every ex-date where the per-share distribution changed by more than
    `threshold` from the prior payment — cuts and raises, annotatable on the
    sentiment-index chart."""
    if dist.empty:
        return pd.DataFrame(columns=["ticker", "ex_date", "amount", "prior_amount", "change", "change_pct"])
    rows = []
    for ticker, grp in dist.groupby("ticker"):
        grp = grp.sort_values("ex_date").reset_index(drop=True)
        grp["prior_amount"] = grp["amount"].shift()
        grp["change"] = grp["amount"] - grp["prior_amount"]
        grp["change_pct"] = grp["change"] / grp["prior_amount"]
        changed = grp[grp["change"].abs() > threshold]
        rows.append(changed[["ex_date", "amount", "prior_amount", "change", "change_pct"]].assign(ticker=ticker))
    if not rows:
        return pd.DataFrame(columns=["ticker", "ex_date", "amount", "prior_amount", "change", "change_pct"])
    return pd.concat(rows, ignore_index=True).sort_values("ex_date")


def run() -> dict[str, pd.DataFrame]:
    dist = distribution_history()
    write_parquet(dist, OUT_HISTORY, Provenance(parser="src.cef.analysis_distributions.distribution_history", source_urls=[]))

    yields = annualized_yield_on_price_and_book(dist)
    write_parquet(yields, OUT_YIELD, Provenance(parser="src.cef.analysis_distributions.annualized_yield_on_price_and_book", source_urls=[]))

    events = distribution_change_events(dist)
    write_parquet(events, OUT_EVENTS, Provenance(parser="src.cef.analysis_distributions.distribution_change_events", source_urls=[]))

    logger.info("history=%d rows, yields=%d funds, change_events=%d", len(dist), len(yields), len(events))
    return {"history": dist, "yields": yields, "events": events}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
