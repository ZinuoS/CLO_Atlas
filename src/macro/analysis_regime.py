"""Rate-regime segmentation and duration-pain quantification (slide 1: "The
regime changed. Most portfolios didn't.").

Three analyses, all computed from cached series (no network here):
  1. Rule-based rate-regime labels on the last ~35 years of FEDFUNDS.
  2. Total-return comparison across AGG/TLT/BKLN/SHV (+ JAAA) since Dec 2021,
     with drawdown depth/recovery status as of the latest cached date.
  3. An illustrative SOFR + spread floater-coupon table vs. AGG's starting
     yield-to-worst proxy each year — labeled illustrative throughout, not a
     real deal's terms.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.macro.analysis_regime")

FRED_PATH = config.INTERIM_DIR / "macro_fred_series.parquet"
ETF_PRICES_PATH = config.INTERIM_DIR / "etf_prices.parquet"
EXTRA_PRICES_PATH = config.INTERIM_DIR / "macro_returns_extra.parquet"

OUT_REGIME = config.FINAL_DIR / "macro_rate_regime.parquet"
OUT_DURATION_GROWTH = config.FINAL_DIR / "macro_duration_pain_growth.parquet"
OUT_DURATION_DRAWDOWN = config.FINAL_DIR / "macro_duration_pain_drawdown.parquet"
OUT_FLOATER_TABLE = config.FINAL_DIR / "macro_floater_mechanics.parquet"

DURATION_TICKERS = ["AGG", "TLT", "BKLN", "SHV", "JAAA"]
DURATION_PAIN_START = "2021-12-01"


def _load_fred() -> pd.DataFrame:
    df = read_parquet(FRED_PATH)
    df["date"] = pd.to_datetime(df["date"])
    return df


def rate_regime_labels() -> pd.DataFrame:
    """Rule-based regime label per month from FEDFUNDS: ZIRP if the level is
    at/below config.MACRO_ZIRP_THRESHOLD_PCT; hiking/easing if the 12-month
    change exceeds config.MACRO_REGIME_ROC_THRESHOLD_PCT in either direction;
    plateau otherwise. Documented thresholds, not a fitted model."""
    fred = _load_fred()
    ff = fred[fred["series"] == "FEDFUNDS"].sort_values("date").dropna(subset=["value"])
    if ff.empty:
        logger.warning("no FEDFUNDS series cached; rate_regime_labels is empty")
        return pd.DataFrame(columns=["date", "fedfunds", "roc_12m", "regime"])

    monthly = ff.set_index("date")["value"].resample("MS").last().ffill()
    roc_12m = monthly.diff(12)

    def _label(level, roc):
        if pd.isna(roc):
            roc = 0.0
        if level <= config.MACRO_ZIRP_THRESHOLD_PCT:
            return "ZIRP"
        if roc >= config.MACRO_REGIME_ROC_THRESHOLD_PCT:
            return "Hiking"
        if roc <= -config.MACRO_REGIME_ROC_THRESHOLD_PCT:
            return "Easing"
        return "Plateau"

    out = pd.DataFrame({"date": monthly.index, "fedfunds": monthly.values, "roc_12m": roc_12m.values})
    out["regime"] = [
        _label(level, roc) for level, roc in zip(out["fedfunds"], out["roc_12m"])
    ]
    return out


def _load_duration_prices() -> pd.DataFrame:
    frames = []
    if ETF_PRICES_PATH.exists():
        etf = read_parquet(ETF_PRICES_PATH)
        etf["date"] = pd.to_datetime(etf["date"])
        frames.append(etf[etf["ticker"].isin(DURATION_TICKERS)])
    if EXTRA_PRICES_PATH.exists():
        extra = read_parquet(EXTRA_PRICES_PATH)
        extra["date"] = pd.to_datetime(extra["date"])
        frames.append(extra[extra["ticker"].isin(DURATION_TICKERS)])
    if not frames:
        return pd.DataFrame(columns=["date", "ticker", "adj_close"])
    prices = pd.concat(frames, ignore_index=True)
    return prices.sort_values(["ticker", "date"])


def duration_pain_growth(prices: pd.DataFrame, start: str = DURATION_PAIN_START) -> pd.DataFrame:
    """Indexed total return of AGG/TLT/BKLN/SHV(+JAAA) from `start` to the
    latest cached date — the "duration bill" panel."""
    if prices.empty:
        logger.warning("no duration-pain price data cached; duration_pain_growth is empty")
        return pd.DataFrame(columns=["date", "ticker", "growth_of_100"])
    start_ts = pd.Timestamp(start)
    rows = []
    for ticker, grp in prices.groupby("ticker"):
        grp = grp[grp["date"] >= start_ts].sort_values("date")
        if grp.empty:
            continue
        rets = grp["adj_close"].pct_change().fillna(0)
        growth = 100 * (1 + rets).cumprod()
        rows.append(pd.DataFrame({"date": grp["date"], "ticker": ticker, "growth_of_100": growth.values}))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["date", "ticker", "growth_of_100"])


def duration_pain_drawdown(prices: pd.DataFrame, start: str = DURATION_PAIN_START) -> pd.DataFrame:
    """Max drawdown and recovery status (as of the latest cached date) per
    ticker across the same window."""
    if prices.empty:
        return pd.DataFrame(columns=["ticker", "max_drawdown", "trough_date", "as_of", "recovered"])
    start_ts = pd.Timestamp(start)
    rows = []
    for ticker, grp in prices.groupby("ticker"):
        grp = grp[grp["date"] >= start_ts].sort_values("date")
        if grp.empty:
            continue
        price = grp["adj_close"].reset_index(drop=True)
        dates = grp["date"].reset_index(drop=True)
        cummax = price.cummax()
        drawdown = price / cummax - 1
        trough_idx = drawdown.idxmin()
        rows.append({
            "ticker": ticker,
            "max_drawdown": drawdown.iloc[trough_idx],
            "trough_date": dates.iloc[trough_idx],
            "as_of": dates.iloc[-1],
            "recovered": bool(price.iloc[-1] >= cummax.iloc[trough_idx]),
        })
    return pd.DataFrame(rows).sort_values("max_drawdown")


def floater_mechanics_table() -> pd.DataFrame:
    """Illustrative SOFR + spread floater coupon path vs. AGG's start-of-year
    yield-to-worst proxy (the IG OAS + matched UST yield). Every spread value
    is labeled illustrative — not any real CLO tranche's actual terms."""
    fred = _load_fred()
    sofr = fred[fred["series"] == "SOFR"].sort_values("date").dropna(subset=["value"])
    ig_oas = fred[fred["series"] == "IG_OAS"].sort_values("date").dropna(subset=["value"])
    ust10 = fred[fred["series"] == "UST_10Y"].sort_values("date").dropna(subset=["value"])
    if sofr.empty or ig_oas.empty or ust10.empty:
        logger.warning("missing SOFR/IG_OAS/UST_10Y; floater_mechanics_table is empty")
        return pd.DataFrame(columns=["year", "sofr_year_avg", "agg_ytw_proxy_year_start"] +
                             [f"coupon_{k.replace(' ', '_')}" for k in config.MACRO_ILLUSTRATIVE_FLOATER_SPREADS_BPS])

    sofr_annual = sofr.set_index("date")["value"].resample("YS").mean()
    ig_oas_start = ig_oas.set_index("date")["value"].resample("YS").first()
    ust10_start = ust10.set_index("date")["value"].resample("YS").first()
    agg_ytw_proxy = (ig_oas_start + ust10_start).dropna()

    years = sofr_annual.index.intersection(agg_ytw_proxy.index)
    out = pd.DataFrame({
        "year": years.year,
        "sofr_year_avg": sofr_annual.loc[years].values,
        "agg_ytw_proxy_year_start": agg_ytw_proxy.loc[years].values,
    })
    for label, bps in config.MACRO_ILLUSTRATIVE_FLOATER_SPREADS_BPS.items():
        col = f"coupon_{label.replace(' ', '_')}"
        out[col] = out["sofr_year_avg"] + bps / 100
    return out


def run() -> dict[str, pd.DataFrame]:
    regime = rate_regime_labels()
    write_parquet(regime, OUT_REGIME, Provenance(parser="src.macro.analysis_regime.rate_regime_labels", source_urls=[]))

    prices = _load_duration_prices()
    growth = duration_pain_growth(prices)
    write_parquet(growth, OUT_DURATION_GROWTH, Provenance(parser="src.macro.analysis_regime.duration_pain_growth", source_urls=[]))

    drawdown = duration_pain_drawdown(prices)
    write_parquet(drawdown, OUT_DURATION_DRAWDOWN, Provenance(parser="src.macro.analysis_regime.duration_pain_drawdown", source_urls=[]))

    floater = floater_mechanics_table()
    write_parquet(floater, OUT_FLOATER_TABLE, Provenance(
        parser="src.macro.analysis_regime.floater_mechanics_table", source_urls=[],
        notes="Illustrative spreads (config.MACRO_ILLUSTRATIVE_FLOATER_SPREADS_BPS) over SOFR, not any real tranche's terms.",
    ))

    logger.info("regime=%d months, duration_growth=%d rows, duration_drawdown=%d tickers, floater_table=%d years",
                len(regime), len(growth), len(drawdown), len(floater))
    return {"regime": regime, "duration_growth": growth, "duration_drawdown": drawdown, "floater_table": floater}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
