"""Total-return comparison: CLO ETFs vs. AGG/HYG/BKLN/LQD/SHV (Section 1).

Fully computable from cached price history (no accretion-over-time
limitation here, unlike flows/dislocation/tranche-panel) since yfinance
provides full historical OHLCV back to each ticker's inception.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.etf.analysis_returns")

PRICES_PATH = config.INTERIM_DIR / "etf_prices.parquet"
FRED_PATH = config.INTERIM_DIR / "fred_series.parquet"

OUT_GROWTH = config.FINAL_DIR / "etf_growth_of_100.parquet"
OUT_VOL = config.FINAL_DIR / "etf_rolling_vol_90d.parquet"
OUT_DRAWDOWN = config.FINAL_DIR / "etf_drawdown_table.parquet"
OUT_SHARPE = config.FINAL_DIR / "etf_sharpe.parquet"
OUT_DD_DURATION = config.FINAL_DIR / "etf_drawdown_duration.parquet"

COMPARISON_SET = list(config.CLO_ETF_TICKERS.keys()) + config.ETF_COMPARISON_TICKERS


def _load_prices() -> pd.DataFrame:
    prices = read_parquet(PRICES_PATH)
    prices = prices[prices["ticker"].isin(COMPARISON_SET)].copy()
    prices["date"] = pd.to_datetime(prices["date"])
    return prices.sort_values(["ticker", "date"])


def growth_of_100(prices: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ticker, grp in prices.groupby("ticker"):
        grp = grp.sort_values("date")
        rets = grp["adj_close"].pct_change().fillna(0)
        growth = 100 * (1 + rets).cumprod()
        rows.append(pd.DataFrame({"date": grp["date"], "ticker": ticker, "growth_of_100": growth.values}))
    return pd.concat(rows, ignore_index=True)


def rolling_vol_90d(prices: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ticker, grp in prices.groupby("ticker"):
        grp = grp.sort_values("date")
        rets = grp["adj_close"].pct_change()
        vol = rets.rolling(90, min_periods=30).std() * np.sqrt(252)
        rows.append(pd.DataFrame({"date": grp["date"], "ticker": ticker, "rolling_vol_90d": vol.values}))
    return pd.concat(rows, ignore_index=True)


def _max_drawdown(series: pd.Series) -> float:
    cummax = series.cummax()
    drawdown = series / cummax - 1
    return drawdown.min()


def drawdown_table(prices: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ticker, grp in prices.groupby("ticker"):
        grp = grp.sort_values("date")
        max_dd = _max_drawdown(grp["adj_close"])
        rows.append({"ticker": ticker, "max_drawdown": max_dd,
                      "n_days": len(grp), "start_date": grp["date"].min(), "end_date": grp["date"].max()})
    return pd.DataFrame(rows).sort_values("max_drawdown")


def sharpe_ratios(prices: pd.DataFrame) -> pd.DataFrame:
    if not FRED_PATH.exists():
        logger.warning("no FRED series cached; Sharpe will use a 0%% risk-free rate")
        rf_annual = 0.0
    else:
        fred = read_parquet(FRED_PATH)
        tbill = fred[fred["series"] == "3M_TBILL"].sort_values("date")
        rf_annual = (tbill["value"].dropna().iloc[-1] / 100) if len(tbill) else 0.0

    rows = []
    for ticker, grp in prices.groupby("ticker"):
        grp = grp.sort_values("date")
        rets = grp["adj_close"].pct_change().dropna()
        if rets.empty or rets.std() == 0:
            continue
        ann_return = (1 + rets.mean()) ** 252 - 1
        ann_vol = rets.std() * np.sqrt(252)
        sharpe = (ann_return - rf_annual) / ann_vol if ann_vol else None
        rows.append({"ticker": ticker, "ann_return": ann_return, "ann_vol": ann_vol,
                      "risk_free_used": rf_annual, "sharpe": sharpe})
    return pd.DataFrame(rows).sort_values("sharpe", ascending=False)


def drawdown_duration_profile(prices: pd.DataFrame) -> pd.DataFrame:
    """For each ticker: every drawdown episode's depth and days-to-recovery
    (first date the price re-exceeds its prior peak); ongoing episodes at the
    end of the series get recovery_days = None."""
    rows = []
    for ticker, grp in prices.groupby("ticker"):
        grp = grp.sort_values("date").reset_index(drop=True)
        price = grp["adj_close"].values
        dates = grp["date"].values
        peak = price[0]
        peak_idx = 0
        in_drawdown = False
        trough = peak
        trough_idx = 0
        for i in range(1, len(price)):
            if price[i] >= peak:
                if in_drawdown:
                    rows.append({
                        "ticker": ticker, "peak_date": dates[peak_idx], "trough_date": dates[trough_idx],
                        "recovery_date": dates[i], "depth": trough / peak - 1,
                        "days_to_trough": trough_idx - peak_idx, "days_to_recovery": i - peak_idx,
                    })
                    in_drawdown = False
                peak = price[i]
                peak_idx = i
                trough = peak
                trough_idx = i
            else:
                in_drawdown = True
                if price[i] < trough:
                    trough = price[i]
                    trough_idx = i
        if in_drawdown:
            rows.append({
                "ticker": ticker, "peak_date": dates[peak_idx], "trough_date": dates[trough_idx],
                "recovery_date": None, "depth": trough / peak - 1,
                "days_to_trough": trough_idx - peak_idx, "days_to_recovery": None,
            })
    return pd.DataFrame(rows)


def run() -> dict[str, pd.DataFrame]:
    prices = _load_prices()

    growth = growth_of_100(prices)
    write_parquet(growth, OUT_GROWTH, Provenance(parser="src.etf.analysis_returns.growth_of_100", source_urls=[]))

    vol = rolling_vol_90d(prices)
    write_parquet(vol, OUT_VOL, Provenance(parser="src.etf.analysis_returns.rolling_vol_90d", source_urls=[]))

    dd = drawdown_table(prices)
    write_parquet(dd, OUT_DRAWDOWN, Provenance(parser="src.etf.analysis_returns.drawdown_table", source_urls=[]))

    sharpe = sharpe_ratios(prices)
    write_parquet(sharpe, OUT_SHARPE, Provenance(parser="src.etf.analysis_returns.sharpe_ratios", source_urls=[]))

    dd_duration = drawdown_duration_profile(prices)
    write_parquet(dd_duration, OUT_DD_DURATION, Provenance(parser="src.etf.analysis_returns.drawdown_duration_profile", source_urls=[]))

    logger.info("growth=%d rows, vol=%d rows, drawdown_table=%d tickers, sharpe=%d tickers, dd_duration=%d episodes",
                len(growth), len(vol), len(dd), len(sharpe), len(dd_duration))
    return {"growth": growth, "vol": vol, "drawdown_table": dd, "sharpe": sharpe, "dd_duration": dd_duration}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
