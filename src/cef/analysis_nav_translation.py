"""How loan-market moves translate into these NAVs (Section 2 deep-dive):
the leverage gradient from AAA CLO ETF through broadly-syndicated loans to
levered CLO-equity CEF NAV and price.

True NAV history isn't available for OXLC/ECC (see analysis_capital_machine.py
and cef/analysis_premium_discount.py's own documented limitation), so "NAV
beta" here uses each fund's MARKET PRICE as the NAV-translation proxy —
labeled as such, not asserted as a true NAV beta. The price-vs-price
comparison across JAAA (AAA CLO ETF, near-zero leverage to loan losses),
BKLN (unlevered loans), and OXLC/ECC (double-levered CLO equity: the deal's
own leverage plus these funds' own preferred/debt leverage on top) is still
the right shape for the "leverage gradient" story even on a price basis.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.cef.analysis_nav_translation")

CEF_PRICES_PATH = config.INTERIM_DIR / "cef_prices.parquet"
ETF_PRICES_PATH = config.INTERIM_DIR / "etf_prices.parquet"

OUT_BETA = config.FINAL_DIR / "nav_translation_beta.parquet"
OUT_DRAWDOWN_LADDER = config.FINAL_DIR / "nav_translation_drawdown_ladder.parquet"

LADDER_TICKERS = ["JAAA", "BKLN", "OXLC", "ECC"]


def _load_prices() -> pd.DataFrame:
    frames = []
    if ETF_PRICES_PATH.exists():
        etf = read_parquet(ETF_PRICES_PATH)
        frames.append(etf[etf["ticker"].isin(["JAAA", "BKLN"])][["date", "ticker", "adj_close"]])
    if CEF_PRICES_PATH.exists():
        cef = read_parquet(CEF_PRICES_PATH)
        frames.append(cef[cef["ticker"].isin(["OXLC", "ECC"])][["date", "ticker", "adj_close"]])
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    return df


def price_beta_to_loans() -> pd.DataFrame:
    """Monthly-return beta of each ticker's price to BKLN (broadly
    syndicated loans) — the leverage-amplification measure."""
    prices = _load_prices()
    if prices.empty:
        return pd.DataFrame(columns=["ticker", "beta_to_bkln", "n_months"])
    monthly = prices.set_index("date").groupby("ticker")["adj_close"].resample("ME").last().reset_index()
    monthly["ret"] = monthly.groupby("ticker")["adj_close"].pct_change()
    wide = monthly.pivot(index="date", columns="ticker", values="ret")
    if "BKLN" not in wide.columns:
        return pd.DataFrame(columns=["ticker", "beta_to_bkln", "n_months"])

    rows = []
    for ticker in LADDER_TICKERS:
        if ticker not in wide.columns or ticker == "BKLN":
            continue
        pair = wide[[ticker, "BKLN"]].dropna()
        if len(pair) < 6:
            continue
        cov = np.cov(pair[ticker], pair["BKLN"])
        beta = cov[0, 1] / cov[1, 1] if cov[1, 1] else None
        rows.append({"ticker": ticker, "beta_to_bkln": beta, "n_months": len(pair)})
    rows.append({"ticker": "BKLN", "beta_to_bkln": 1.0, "n_months": len(wide["BKLN"].dropna())})
    return pd.DataFrame(rows)


def drawdown_ladder(start: str = "2020-01-01") -> pd.DataFrame:
    """Max drawdown per ticker from `start` — the same "duration bill"-style
    max-drawdown computation the macro section uses, applied to the
    leverage-gradient ladder instead of the rate-regime comparison."""
    prices = _load_prices()
    if prices.empty:
        return pd.DataFrame(columns=["ticker", "max_drawdown", "trough_date"])
    prices = prices[prices["date"] >= pd.Timestamp(start)]
    rows = []
    for ticker in LADDER_TICKERS:
        sub = prices[prices["ticker"] == ticker].sort_values("date")
        if sub.empty:
            continue
        cummax = sub["adj_close"].cummax()
        drawdown = sub["adj_close"] / cummax - 1
        trough_idx = drawdown.values.argmin()
        rows.append({"ticker": ticker, "max_drawdown": drawdown.iloc[trough_idx],
                     "trough_date": sub["date"].iloc[trough_idx]})
    return pd.DataFrame(rows)


def run() -> dict[str, pd.DataFrame]:
    beta = price_beta_to_loans()
    write_parquet(beta, OUT_BETA, Provenance(
        parser="src.cef.analysis_nav_translation.price_beta_to_loans", source_urls=[],
        notes="Price beta, not true NAV beta — historical NAV isn't available for OXLC/ECC (see module docstring).",
    ))

    ladder = drawdown_ladder()
    write_parquet(ladder, OUT_DRAWDOWN_LADDER, Provenance(parser="src.cef.analysis_nav_translation.drawdown_ladder", source_urls=[]))

    logger.info("beta=%d tickers, drawdown_ladder=%d tickers", len(beta), len(ladder))
    return {"beta": beta, "drawdown_ladder": ladder}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
