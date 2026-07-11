"""Slide 2 exhibit (left panel): bank vs. nonbank share of corporate lending
since 1945, structural landmarks flagged, with a companion loans-vs-bonds
mix panel.
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, INK_MUTED, WARM_GRAY, apply_theme, save_figure
from src.macro.analysis_disintermediation import STRUCTURAL_LANDMARKS

logger = logging.getLogger("clo_atlas.macro.viz_disintermediation")

NONBANK_SHARE_PATH = config.FINAL_DIR / "macro_nonbank_lending_share.parquet"
LOANS_VS_BONDS_PATH = config.FINAL_DIR / "macro_loans_vs_bonds_mix.parquet"


def _flag_landmarks(ax, headroom: float = 0.22):
    """Dashed lines through the plot area; labels live in whitespace added
    above the data range (data tops out at 1.0/100%) so text never sits on
    top of the filled area."""
    ymin, ymax = ax.get_ylim()
    ax.set_ylim(ymin, ymax + headroom)
    for ev in STRUCTURAL_LANDMARKS:
        d = pd.Timestamp(ev["date"])
        ax.axvline(d, ymin=0, ymax=(ymax - ymin) / (ymax - ymin + headroom), color=WARM_GRAY[2], lw=1, linestyle="--", zorder=1)
        ax.annotate(ev["label"], xy=(d, ymax + headroom * 0.08), rotation=90,
                    fontsize=7.5, color=INK_MUTED, ha="right", va="bottom")


def viz_nonbank_share_stacked():
    apply_theme()
    df = read_parquet(NONBANK_SHARE_PATH)
    if df.empty:
        logger.warning("no nonbank-share data; skipping viz_nonbank_share_stacked")
        return None
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    bank_share = 1 - df["nonbank_share"]
    ax.stackplot(df["date"], bank_share, df["nonbank_share"],
                 colors=[WARM_GRAY[2], ACCENT], alpha=0.9, labels=["Banks", "Nonbanks"])
    ax.set_ylim(0, 1)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")

    latest = df.iloc[-1]
    latest_quarter = (latest["date"].month - 1) // 3 + 1
    ax.annotate(f"{latest['nonbank_share']:.0%} nonbank\nas of {latest['date'].year} Q{latest_quarter}",
                xy=(latest["date"], 1 - latest["nonbank_share"] / 2), xytext=(-130, 0),
                textcoords="offset points", fontsize=9.5, color="white", fontweight="bold",
                ha="left", va="center")

    _flag_landmarks(ax)

    ax.xaxis.set_major_locator(mdates.YearLocator(10))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.legend(loc="lower left", fontsize=9, frameon=False)
    ax.set_ylabel("Share of nonfinancial corporate loans outstanding")
    png, svg = save_figure(
        fig, "viz_nonbank_share_stacked",
        headline="Banks used to make most corporate loans. Now nonbanks do.",
        subtitle="Share of nonfinancial corporate business loans held by depository institutions vs. all other lenders, 1945-present.",
        source="clo-atlas, from FRED (Z.1 Financial Accounts, BOGZ1 series)",
        notes="\"Nonbanks\" = total loans (credit market debt minus debt securities) minus depository-institution loans; residual includes CLOs, "
              "finance companies, BDCs, and other nonbank lenders combined, not CLOs alone.",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def viz_loans_vs_bonds_mix():
    apply_theme()
    df = read_parquet(LOANS_VS_BONDS_PATH)
    if df.empty:
        logger.warning("no loans-vs-bonds data; skipping viz_loans_vs_bonds_mix")
        return None
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    fig, ax = plt.subplots(figsize=(9.5, 3.2))
    ax.stackplot(df["date"], df["loans_share"], df["bonds_share"],
                 colors=[WARM_GRAY[1], WARM_GRAY[3]], alpha=0.95, labels=["Loans", "Bonds"])
    ax.set_ylim(0, 1)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.xaxis.set_major_locator(mdates.YearLocator(10))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.legend(loc="lower left", fontsize=9, frameon=False, ncol=2)
    ax.set_ylabel("Share of debt")
    png, svg = save_figure(
        fig, "viz_loans_vs_bonds_mix",
        headline="The loans-vs-bonds mix in corporate debt has been far steadier than who lends it.",
        subtitle="Loans vs. debt securities share of nonfinancial corporate business debt outstanding, 1945-present.",
        source="clo-atlas, from FRED (Z.1 Financial Accounts, BOGZ1 series)",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_nonbank_share_stacked()
    viz_loans_vs_bonds_mix()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
