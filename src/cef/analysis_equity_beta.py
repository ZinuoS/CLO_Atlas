"""Does the CEF wrapper carry more equity beta than the underlying CLO
paper? (Section 2)

Price beta vs. SPY/HYG is fully computable from real full-history price
data. Book-value (NAV proxy) beta needs multi-date book-value history, which
today is a single snapshot (see scrape_prices_nav.py) — that half degrades
gracefully until enough daily runs accrete.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

import config
from src.cef.scrape_prices_nav import BETA_COMPARISON_TICKERS
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.cef.analysis_equity_beta")

PRICES_PATH = config.INTERIM_DIR / "cef_prices.parquet"
SNAPSHOTS_PATH = config.INTERIM_DIR / "cef_bookvalue_snapshots.parquet"

OUT_PRICE_BETA = config.FINAL_DIR / "cef_price_beta.parquet"
OUT_VOL_RATIO = config.FINAL_DIR / "cef_price_vs_book_vol_ratio.parquet"

ROLLING_WINDOW = 90


def _rolling_beta(returns: pd.Series, bench_returns: pd.Series, window: int) -> pd.Series:
    cov = returns.rolling(window).cov(bench_returns)
    var = bench_returns.rolling(window).var()
    return cov / var


def rolling_price_beta(benchmark: str = "HYG") -> pd.DataFrame:
    if not PRICES_PATH.exists():
        logger.warning("no CEF price history cached; run scrape_prices_nav.py first")
        return pd.DataFrame(columns=["date", "ticker", "beta"])
    prices = read_parquet(PRICES_PATH)
    if benchmark not in prices["ticker"].unique():
        logger.warning("benchmark %s not in cached price history; skipping rolling_price_beta", benchmark)
        return pd.DataFrame(columns=["date", "ticker", "beta"])

    bench = prices[prices["ticker"] == benchmark].sort_values("date").set_index("date")["adj_close"].pct_change()
    rows = []
    for ticker in config.CLO_CEF_TICKERS:
        sub = prices[prices["ticker"] == ticker].sort_values("date").set_index("date")["adj_close"].pct_change()
        aligned = pd.concat([sub, bench], axis=1, keys=["fund", "bench"]).dropna()
        if len(aligned) < ROLLING_WINDOW:
            logger.info("%s: only %d overlapping days with %s (<%d needed); skipping", ticker, len(aligned), benchmark, ROLLING_WINDOW)
            continue
        beta = _rolling_beta(aligned["fund"], aligned["bench"], ROLLING_WINDOW)
        rows.append(pd.DataFrame({"date": beta.index, "ticker": ticker, "benchmark": benchmark, "beta": beta.values}))
    if not rows:
        return pd.DataFrame(columns=["date", "ticker", "benchmark", "beta"])
    return pd.concat(rows, ignore_index=True).dropna()


def price_vs_book_vol_ratio() -> pd.DataFrame:
    """Ratio of price volatility to book-value volatility per fund — "the
    wrapper is the risk" exhibit. Needs multi-date book-value history;
    returns empty (not fabricated) until scrape_prices_nav.py has run on
    enough distinct days.
    """
    if not SNAPSHOTS_PATH.exists():
        return pd.DataFrame(columns=["ticker", "price_vol", "book_vol", "vol_ratio"])
    snaps = read_parquet(SNAPSHOTS_PATH).dropna(subset=["book_value_per_share"])
    if snaps["date"].nunique() < 30:
        logger.warning("book-value history has only %d distinct date(s); need ~30 for a stable vol ratio. "
                        "Run scrape_prices_nav.py again on more days.", snaps["date"].nunique())
        return pd.DataFrame(columns=["ticker", "price_vol", "book_vol", "vol_ratio"])

    prices = read_parquet(PRICES_PATH)
    rows = []
    for ticker, grp in snaps.groupby("ticker"):
        book_vol = grp.sort_values("date")["book_value_per_share"].pct_change().std()
        price_hist = prices[prices["ticker"] == ticker].sort_values("date")
        price_vol = price_hist["adj_close"].pct_change().std()
        rows.append({"ticker": ticker, "price_vol": price_vol, "book_vol": book_vol,
                      "vol_ratio": (price_vol / book_vol) if book_vol else None})
    return pd.DataFrame(rows)


def run() -> dict[str, pd.DataFrame]:
    beta = rolling_price_beta()
    write_parquet(beta, OUT_PRICE_BETA, Provenance(parser="src.cef.analysis_equity_beta.rolling_price_beta", source_urls=[]))

    vol_ratio = price_vs_book_vol_ratio()
    write_parquet(vol_ratio, OUT_VOL_RATIO, Provenance(parser="src.cef.analysis_equity_beta.price_vs_book_vol_ratio", source_urls=[]))

    logger.info("price_beta=%d rows, vol_ratio=%d funds", len(beta), len(vol_ratio))
    return {"beta": beta, "vol_ratio": vol_ratio}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
