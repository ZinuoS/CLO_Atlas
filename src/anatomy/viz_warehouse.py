"""Warehouse ramp-up: how the pre-closing portfolio is financed (debt vs.
at-risk equity capital) as it accumulates toward the deal's target par, and
what that capital earns before the CLO ever prices.

Timing (the x-axis, both panels) is real: the circular's Issuer-history
section gives the entity's actual incorporation date and Original Closing
Date. Dollar figures (the stack heights, the carry) are illustrative --
warehouse lending economics are never disclosed in a public offering
circular, for any CLO. The two are marked differently on purpose (hatched
fill + "ILLUSTRATIVE ECONOMICS" in the subtitle, not just a footnote) so
the real part and the estimated part can't be mistaken for each other at a
glance. See analysis_warehouse.py's module docstring for the full citation.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

import config
from src.anatomy.analysis_warehouse import build_warehouse_schedule
from src.anatomy.deal import Deal, load_deal
from src.common.style import ACCENT, BG, INK, INK_MUTED, WARM_GRAY, apply_theme, save_figure


def build_warehouse_ramp_chart(deal: Deal, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir or config.FIGURES_ANATOMY_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = build_warehouse_schedule(deal)
    hist = config.ANATOMY_ORIGINAL_HISTORY

    apply_theme()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.6), facecolor=BG, gridspec_kw={"width_ratios": [1.5, 1]})

    ax1.stackplot(df["date"], df["warehouse_debt_drawn"] / 1e6, df["equity_at_risk"] / 1e6,
                  colors=[WARM_GRAY[2], ACCENT], hatch="////", edgecolor=BG, linewidth=0.4,
                  labels=["Warehouse debt (illustrative $)", "At-risk equity capital (illustrative $)"])
    original_closing = pd.Timestamp(df.attrs["original_closing_date"])
    ax1.axvline(original_closing, color=INK, lw=1.2, linestyle="--")
    ax1.annotate(f"{original_closing.strftime('%b %-d, %Y')}: Original Closing Date\n(CLO takes out the warehouse) -- VERIFIED date",
                 xy=(original_closing, df["cumulative_par"].max() / 1e6),
                 xytext=(-235, -15), textcoords="offset points", fontsize=7.8, color=INK,
                 arrowprops=dict(arrowstyle="-", color=INK_MUTED, lw=0.8))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b %-d"))
    ax1.set_xlabel(f"{pd.Timestamp(df.attrs['ramp_start_date']).year} (real dates -- VERIFIED)")
    ax1.set_ylabel("$ millions (illustrative)")
    ax1.set_title("Ramping the portfolio: real dates, illustrative $ amounts", fontsize=10, fontweight="bold",
                   color=INK, loc="left")
    ax1.legend(loc="upper left", frameon=False, fontsize=8)

    ax2.plot(df["date"], df["cumulative_net_carry"] / 1e6, color=ACCENT, marker="o", markersize=4, linestyle="--")
    ax2.axhline(0, color=INK_MUTED, lw=0.8)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %-d"))
    ax2.set_xlabel(f"{pd.Timestamp(df.attrs['ramp_start_date']).year} (real dates -- VERIFIED)")
    ax2.set_ylabel("$ millions (illustrative)")
    ax2.set_title("Cumulative carry: illustrative $, real dates", fontsize=10, fontweight="bold", color=INK, loc="left")
    for spine in ("top", "right"):
        ax1.spines[spine].set_visible(False)
        ax2.spines[spine].set_visible(False)

    peak_equity = df.attrs["max_equity_at_risk"]
    clo_equity = df.attrs["clo_equity_size"]
    pct = df.attrs["equity_at_risk_pct_of_clo_equity"]
    total_carry = df.attrs["total_ramp_carry_to_equity"]
    ramp_days = df.attrs["ramp_days"]

    png, svg = save_figure(
        fig, "warehouse_ramp",
        headline=f"Before the CLO existed, a {ramp_days}-day warehouse ramped the portfolio -- ILLUSTRATIVE ECONOMICS on REAL dates.",
        subtitle=f"VERIFIED: incorporated as \"{hist['original_entity_name']}\" on {hist['incorporation_date']}, "
                 f"Original Closing Date {hist['original_closing_date']} ({ramp_days} days). ILLUSTRATIVE: peak at-risk "
                 f"equity of \\${peak_equity/1e6:.1f}mm ({pct:.0f}% of the \\${clo_equity/1e6:.1f}mm CLO equity tranche) "
                 f"earning \\${total_carry/1e6:.1f}mm of carry -- the hatched fill marks every dollar figure on this chart "
                 "as a market-standard convention, not a disclosed number.",
        source=f"dates: {deal.citation.get('deal_name', '')} refinancing circular, Issuer-history section (VERIFIED); "
                "$ amounts: market-standard warehouse convention (TO-VERIFY, not disclosed)",
        notes="The Issuer's own circular states \"The Issuer does not publish any financial statements,\" and ongoing "
              "investor reporting runs through a restricted third-party platform (Findox) and the Collateral Trustee's "
              "own website, not a public one -- warehouse economics specifically are never disclosed, for any CLO, as "
              "a structural feature of the market, not a gap in this project's research. See the notebook's disclosure "
              "summary for the full public-vs-not breakdown.",
        out_dir=out_dir,
    )
    return png


def main():
    print(f"wrote {run()}")


def run(deal: Deal | None = None) -> Path:
    deal = deal or load_deal()
    return build_warehouse_ramp_chart(deal)


if __name__ == "__main__":
    main()
