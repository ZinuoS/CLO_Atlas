"""StockTwits public API (free, no key) — self-labeled bullish/bearish
retail sentiment for CLO ETF/CEF tickers. Messages carry an optional
`entities.sentiment.basic` tag ("Bullish"/"Bearish") set by the poster
themselves — free ground-truth retail sentiment, not inferred.
"""
from __future__ import annotations

import datetime as dt
import logging

import pandas as pd

import config
from src.common.cache import Provenance, write_parquet
from src.common.http import CachedSession

logger = logging.getLogger("clo_atlas.sentiment.scrape_stocktwits")

OUT_PATH = config.INTERIM_DIR / "stocktwits_messages.parquet"
API_URL = "https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"

STOCKTWITS_TICKERS = ["JAAA", "ECC", "OXLC", "XFLT"]


def scrape_stocktwits(session: CachedSession, tickers: list[str] | None = None) -> pd.DataFrame:
    tickers = tickers or STOCKTWITS_TICKERS
    rows = []
    for ticker in tickers:
        result = session.get(API_URL.format(ticker=ticker))
        if result.status != 200:
            logger.warning("StockTwits %s failed (status %d)", ticker, result.status)
            continue
        payload = result.json()
        for msg in payload.get("messages", []):
            sentiment = (msg.get("entities") or {}).get("sentiment")
            rows.append({
                "ticker": ticker, "message_id": msg.get("id"), "created_at": msg.get("created_at"),
                "body": msg.get("body"), "sentiment_label": sentiment.get("basic") if sentiment else None,
            })
        logger.info("StockTwits %s: %d messages", ticker, len(payload.get("messages", [])))
    return pd.DataFrame(rows)


def bull_bear_ratio(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["ticker", "n_bullish", "n_bearish", "n_labeled", "n_total", "bull_ratio"])
    labeled = df.dropna(subset=["sentiment_label"])
    out = labeled.groupby("ticker")["sentiment_label"].value_counts().unstack(fill_value=0).reset_index()
    out = out.rename(columns={"Bullish": "n_bullish", "Bearish": "n_bearish"})
    for col in ("n_bullish", "n_bearish"):
        if col not in out.columns:
            out[col] = 0
    out["n_labeled"] = out["n_bullish"] + out["n_bearish"]
    out["n_total"] = df.groupby("ticker").size().reindex(out["ticker"]).values
    out["bull_ratio"] = out["n_bullish"] / out["n_labeled"].replace(0, pd.NA)
    return out[["ticker", "n_bullish", "n_bearish", "n_labeled", "n_total", "bull_ratio"]]


def run() -> pd.DataFrame:
    session = CachedSession()
    df = scrape_stocktwits(session)
    if OUT_PATH.exists():
        existing = pd.read_parquet(OUT_PATH)
        df = pd.concat([existing, df], ignore_index=True).drop_duplicates(subset=["message_id"])
    write_parquet(df, OUT_PATH, Provenance(
        source_urls=[API_URL], scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.sentiment.scrape_stocktwits",
        notes="Self-labeled bullish/bearish tags where posters set them; most messages are unlabeled. "
              "Only the most recent ~30 messages per symbol are available per call — accretes across repeated runs.",
    ))
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
