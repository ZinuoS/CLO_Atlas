"""Master daily attention/tone series (Section 6 v2) — the backbone
everything else annotates. GDELT (daily volume + tone) is the intended
primary layer; when it's unavailable (persistently rate-limited from this
project's sandboxed egress — see docs/excluded_sources.md), the headline
corpus (Google News RSS + yfinance ticker news) stands in as the attention
proxy via daily mention counts, domain-scored for tone the same way
regulator text is scored (`scoring.score_section_domain`), so the two
proxies are at least methodologically consistent with each other.

Attention (volume) and tone are reported as separate dimensions on purpose
— coverage spiking without tone moving (or vice versa) is the whole point
of not collapsing them into one number (see analysis_alarm_v2.py for the
same principle applied to the regulator corpus).
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet
from src.sentiment.scoring import score_section_domain, try_load_lm

logger = logging.getLogger("clo_atlas.sentiment.analysis_attention_tone")

GDELT_PATH = config.INTERIM_DIR / "gdelt_timelines.parquet"
NEWS_PATH = config.INTERIM_DIR / "news_headlines.parquet"
YF_NEWS_PATH = config.INTERIM_DIR / "yf_ticker_news.parquet"

OUT_GDELT_DAILY = config.FINAL_DIR / "attention_gdelt_daily.parquet"
OUT_HEADLINE_DAILY = config.FINAL_DIR / "attention_headline_daily.parquet"
OUT_MASTER = config.FINAL_DIR / "attention_tone_master.parquet"


def gdelt_daily() -> pd.DataFrame:
    if not GDELT_PATH.exists():
        return pd.DataFrame(columns=["date", "query", "volume", "tone"])
    df = read_parquet(GDELT_PATH)
    if df.empty:
        logger.warning("gdelt_timelines.parquet is empty (GDELT unreachable this run) — "
                        "attention backbone falls back to the headline-count proxy")
        return pd.DataFrame(columns=["date", "query", "volume", "tone"])
    df["day"] = df["date"].dt.date
    wide = df.pivot_table(index=["day", "query"], columns="mode", values="value", aggfunc="mean").reset_index()
    wide = wide.rename(columns={"day": "date", "timelinevol": "volume", "timelinetone": "tone"})
    return wide


def headline_daily() -> pd.DataFrame:
    """Daily headline count (attention proxy) + mean domain tone score
    across all headline titles that day, pooling the news-RSS and
    yfinance-ticker-news corpora."""
    frames = []
    if NEWS_PATH.exists():
        news = read_parquet(NEWS_PATH)
        if len(news):
            news = news.rename(columns={"published_dt": "dt"})[["title", "dt"]]
            frames.append(news)
    if YF_NEWS_PATH.exists():
        yf_news = read_parquet(YF_NEWS_PATH)
        if len(yf_news):
            yf_news = yf_news.rename(columns={"pub_date": "dt"})[["title", "dt"]]
            frames.append(yf_news)
    if not frames:
        logger.warning("no headline corpora cached; run scrape_news_rss.py / scrape_yf_news.py first")
        return pd.DataFrame(columns=["date", "n_headlines", "mean_vulnerability_rate", "mean_lm_negative_rate"])

    headlines = pd.concat(frames, ignore_index=True).dropna(subset=["dt"])
    headlines["date"] = pd.to_datetime(headlines["dt"]).dt.date

    lm = try_load_lm()
    scores = headlines["title"].apply(lambda t: score_section_domain(t, lm))
    headlines["vulnerability_rate"] = scores.apply(lambda s: s["vulnerability_rate"])
    headlines["lm_negative_rate"] = scores.apply(lambda s: s["lm_negative_rate"])

    daily = headlines.groupby("date").agg(
        n_headlines=("title", "count"),
        mean_vulnerability_rate=("vulnerability_rate", "mean"),
        mean_lm_negative_rate=("lm_negative_rate", "mean"),
    ).reset_index()
    return daily


def run() -> dict[str, pd.DataFrame]:
    gdelt = gdelt_daily()
    write_parquet(gdelt, OUT_GDELT_DAILY, Provenance(parser="src.sentiment.analysis_attention_tone.gdelt_daily", source_urls=[]))

    headline = headline_daily()
    write_parquet(headline, OUT_HEADLINE_DAILY, Provenance(
        parser="src.sentiment.analysis_attention_tone.headline_daily", source_urls=[],
        notes="Attention/tone proxy used when GDELT is unavailable; domain-scored the same way as regulator text.",
    ))

    logger.info("gdelt_daily=%d rows (%s), headline_daily=%d days",
                len(gdelt), "GDELT reachable" if len(gdelt) else "GDELT unreachable, using headline proxy", len(headline))
    return {"gdelt_daily": gdelt, "headline_daily": headline}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
