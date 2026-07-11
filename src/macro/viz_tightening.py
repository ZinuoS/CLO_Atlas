"""Bank credit tightening exhibits (slide 2 supporting material).

(a) SLOOS net tightening as an area chart oscillating around zero, recessions
    (USREC) shaded, current value flagged with its historical percentile.
(b) SLOOS-vs-lending-growth cross-correlation by lead, the real (descriptive,
    non-causal) finding computed here.
(c) SLOOS vs. HY OAS scatter — the honest version of the planned CLO-issuance
    overlay, which could not be built (see analysis_tightening.py docstring:
    Section 4's CLO issuance series is empty because SIFMA is gated).
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import pandas as pd

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, INK, INK_MUTED, WARM_GRAY, apply_theme, format_date_axis, save_figure

logger = logging.getLogger("clo_atlas.macro.viz_tightening")

FRED_PATH = config.INTERIM_DIR / "macro_fred_series.parquet"
SLOOS_HISTORY_PATH = config.FINAL_DIR / "macro_sloos_history.parquet"
XCORR_PATH = config.FINAL_DIR / "macro_sloos_vs_lending_xcorr.parquet"
SPREADS_PATH = config.FINAL_DIR / "macro_sloos_vs_spreads.parquet"


def _recession_spans() -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    fred = read_parquet(FRED_PATH)
    fred["date"] = pd.to_datetime(fred["date"])
    usrec = fred[fred["series"] == "USREC"].sort_values("date").dropna(subset=["value"])
    if usrec.empty:
        return []
    usrec = usrec.set_index("date")["value"]
    in_rec = usrec > 0
    starts = usrec.index[in_rec & ~in_rec.shift(1, fill_value=False)]
    ends = usrec.index[in_rec & ~in_rec.shift(-1, fill_value=False)]
    return list(zip(starts, ends))


def viz_sloos_history():
    apply_theme()
    df = read_parquet(SLOOS_HISTORY_PATH)
    if df.empty:
        logger.warning("no SLOOS history; skipping viz_sloos_history")
        return None
    df["date"] = pd.to_datetime(df["date"])

    date_min, date_max = df["date"].min(), df["date"].max()
    fig, ax = plt.subplots(figsize=(9.5, 5))
    for start, end in _recession_spans():
        if end < date_min or start > date_max:
            continue
        ax.axvspan(max(start, date_min), min(end, date_max), color=WARM_GRAY[2], alpha=0.3, lw=0, zorder=0)
    ax.set_xlim(date_min, date_max)

    tightening = df["net_pct_tightening"].clip(lower=0)
    easing = df["net_pct_tightening"].clip(upper=0)
    ax.fill_between(df["date"], tightening, 0, color=ACCENT, alpha=0.85, step=None, label="Net tightening")
    ax.fill_between(df["date"], easing, 0, color=WARM_GRAY[1], alpha=0.85, step=None, label="Net easing")
    ax.axhline(0, color=INK, linewidth=0.9)

    latest = df.iloc[-1]
    ax.annotate(f"Latest: {latest['net_pct_tightening']:.0f} (higher = more banks tightening)\n"
                f"{latest['percentile']:.0%}ile of this series' full history",
                xy=(latest["date"], latest["net_pct_tightening"]), xytext=(-190, 20),
                textcoords="offset points", fontsize=9, color=INK,
                arrowprops=dict(arrowstyle="->", color=INK_MUTED, lw=1))

    format_date_axis(ax, interval_months=48)
    ax.set_ylabel("Net % of banks tightening C&I lending standards")
    ax.legend(loc="upper left", fontsize=9, frameon=False)
    png, svg = save_figure(
        fig, "viz_sloos_history",
        headline="Banks tighten sharply around every recession, then ease back — that cycle hasn't changed.",
        subtitle="Net percentage of large/medium banks reporting tighter C&I lending standards (SLOOS), recessions shaded.",
        source="clo-atlas, from FRED (DRTSCILM, USREC)",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def viz_sloos_lending_xcorr():
    apply_theme()
    df = read_parquet(XCORR_PATH)
    if df.empty:
        logger.warning("no cross-correlation data; skipping viz_sloos_lending_xcorr")
        return None

    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.bar(df["lead_quarters"], df["correlation"], color=ACCENT, width=0.55)
    ax.axhline(0, color=INK, linewidth=0.9)
    for _, row in df.iterrows():
        ax.annotate(f"{row['correlation']:.2f}", xy=(row["lead_quarters"], row["correlation"]),
                    xytext=(0, -12 if row["correlation"] < 0 else 6), textcoords="offset points",
                    ha="center", fontsize=9, color=INK)
    ax.set_xticks(df["lead_quarters"])
    ax.set_ylim(df["correlation"].min() * 1.25, max(df["correlation"].max() * 1.25, 0.05))
    ax.set_xlabel("SLOOS tightening, led by N quarters")
    ax.set_ylabel("Correlation with y/y C&I loan growth")
    png, svg = save_figure(
        fig, "viz_sloos_lending_xcorr",
        headline="Bank tightening shows up in the loan-growth data about a year later.",
        subtitle="Cross-correlation of SLOOS net tightening (large/medium firms) with year-over-year C&I loan growth, by lead. Descriptive only, not a causal estimate.",
        source="clo-atlas, from FRED (DRTSCILM, BUSLOANS)",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def viz_sloos_vs_spreads():
    apply_theme()
    df = read_parquet(SPREADS_PATH)
    if df.empty:
        logger.warning("no SLOOS-vs-spreads data; skipping viz_sloos_vs_spreads")
        return None
    n_decades = df["decade"].nunique()

    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    if n_decades > 1:
        for decade, grp in df.groupby("decade"):
            ax.scatter(grp["net_pct_tightening"], grp["hy_oas"], label=str(int(decade)), alpha=0.85, s=60)
        ax.legend(title="Decade", fontsize=8.5, frameon=False)
    else:
        ax.scatter(df["net_pct_tightening"], df["hy_oas"], c=df.index, cmap="Reds", alpha=0.9, s=60)

    ax.set_xlabel("SLOOS net % tightening")
    ax.set_ylabel("HY OAS (%)")
    notes = ""
    if n_decades <= 1:
        notes = (f"HY-OAS free history here starts {pd.to_datetime(df['date']).min().date()}, so decade-color coding "
                 "collapses to one color; shown chronologically (darker = more recent) instead.")
    png, svg = save_figure(
        fig, "viz_sloos_vs_spreads",
        headline="Bank caution and market pricing don't always agree — that gap is where nonbank lenders live.",
        subtitle="SLOOS net % tightening (large/medium firms) vs. high-yield OAS, quarterly.",
        source="clo-atlas, from FRED (DRTSCILM, BAMLH0A0HYM2)",
        notes=notes,
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_sloos_history()
    viz_sloos_lending_xcorr()
    viz_sloos_vs_spreads()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
