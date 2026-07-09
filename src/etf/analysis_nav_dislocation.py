"""Premium/discount dislocation analysis for CLO ETFs (Section 1).

Like analysis_flows.py, the time-series pieces here (rolling z-scores,
episode detection, recovery half-life) need NAV history that only starts
accreting once scrape_nav_flows.py has been run on multiple distinct days —
see that module's docstring for why no free source back-fills historical
daily NAV for these funds. Every function below degrades gracefully to
"insufficient history yet" rather than fabricating a longer series, and the
cross-sectional (single-day) premium/discount read is always computed since
it needs only today's snapshot.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.etf.analysis_nav_dislocation")

SNAPSHOTS_PATH = config.INTERIM_DIR / "etf_nav_snapshots.parquet"

OUT_DAILY = config.FINAL_DIR / "etf_premium_discount_daily.parquet"
OUT_STATS = config.FINAL_DIR / "etf_premium_discount_stats.parquet"
OUT_EPISODES = config.FINAL_DIR / "etf_dislocation_episodes.parquet"

MIN_HISTORY_FOR_ROLLING = 30  # trading days; below this, rolling z-scores are not meaningful
Z_THRESHOLD = 3.0
RECOVERY_THRESHOLD_BPS = 10  # "recovered" = back within 10bp of its own trailing median


def premium_discount_daily() -> pd.DataFrame:
    if not SNAPSHOTS_PATH.exists():
        logger.warning("no NAV snapshot history cached yet; premium_discount_daily will be empty")
        return pd.DataFrame(columns=["date", "ticker", "market_price", "nav", "premium_discount"])
    snaps = read_parquet(SNAPSHOTS_PATH).dropna(subset=["market_price", "nav"])
    snaps = snaps.copy()
    snaps["premium_discount"] = snaps["market_price"] / snaps["nav"] - 1
    return snaps[["date", "ticker", "market_price", "nav", "premium_discount"]].sort_values(["ticker", "date"])


def dislocation_stats(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame(columns=["ticker", "n_obs", "mean_pd", "std_pd", "min_pd", "max_pd"])
    stats = daily.groupby("ticker")["premium_discount"].agg(
        n_obs="count", mean_pd="mean", std_pd="std", min_pd="min", max_pd="max"
    ).reset_index()
    thin = stats["n_obs"] < MIN_HISTORY_FOR_ROLLING
    if thin.any():
        logger.warning("%d fund(s) have <%d days of NAV history; distribution stats are provisional: %s",
                        thin.sum(), MIN_HISTORY_FOR_ROLLING, stats.loc[thin, "ticker"].tolist())
    return stats


def _exp_recovery(t, a, tau):
    return a * np.exp(-t / tau)


def detect_episodes(daily: pd.DataFrame) -> pd.DataFrame:
    """|z| > Z_THRESHOLD on a rolling 250d window flags an episode; depth =
    peak |premium_discount| in the episode; recovery half-life fit via a
    simple exponential decay of |premium_discount| back toward zero.
    Requires >= MIN_HISTORY_FOR_ROLLING observations per fund; returns an
    empty, clearly-labeled frame for funds below that (which today is all of
    them, on the project's first run).
    """
    if daily.empty:
        return pd.DataFrame(columns=["ticker", "episode_start", "episode_end", "depth", "recovery_half_life_days"])

    rows = []
    for ticker, grp in daily.groupby("ticker"):
        grp = grp.sort_values("date").reset_index(drop=True)
        if len(grp) < MIN_HISTORY_FOR_ROLLING:
            logger.info("%s: only %d NAV observations (<%d needed); skipping episode detection for now",
                        ticker, len(grp), MIN_HISTORY_FOR_ROLLING)
            continue

        roll = grp["premium_discount"].rolling(250, min_periods=MIN_HISTORY_FOR_ROLLING)
        z = (grp["premium_discount"] - roll.mean()) / roll.std()
        flagged = grp[z.abs() > Z_THRESHOLD]
        for _, ep_start_row in flagged.iterrows():
            start_idx = ep_start_row.name
            depth = ep_start_row["premium_discount"]
            window = grp.loc[start_idx:start_idx + 60]
            t = np.arange(len(window))
            y = window["premium_discount"].abs().values
            try:
                popt, _ = curve_fit(_exp_recovery, t, y, p0=[abs(depth), 10], maxfev=2000)
                half_life = popt[1] * np.log(2)
            except Exception:
                half_life = None
            rows.append({
                "ticker": ticker, "episode_start": ep_start_row["date"],
                "episode_end": window["date"].iloc[-1] if len(window) else None,
                "depth": depth, "recovery_half_life_days": half_life,
            })
    return pd.DataFrame(rows)


def run() -> dict[str, pd.DataFrame]:
    daily = premium_discount_daily()
    write_parquet(daily, OUT_DAILY, Provenance(parser="src.etf.analysis_nav_dislocation.premium_discount_daily", source_urls=[]))

    stats = dislocation_stats(daily)
    write_parquet(stats, OUT_STATS, Provenance(parser="src.etf.analysis_nav_dislocation.dislocation_stats", source_urls=[]))

    episodes = detect_episodes(daily)
    write_parquet(episodes, OUT_EPISODES, Provenance(parser="src.etf.analysis_nav_dislocation.detect_episodes", source_urls=[]))

    logger.info("premium_discount_daily=%d rows, stats=%d funds, episodes=%d", len(daily), len(stats), len(episodes))
    return {"daily": daily, "stats": stats, "episodes": episodes}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
