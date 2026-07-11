"""Warehouse ramp-up: how the pre-closing portfolio is financed (debt vs.
at-risk equity capital) as it accumulates toward the deal's target par, and
what that capital earns before the CLO ever prices.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

import config
from src.anatomy.analysis_warehouse import build_warehouse_schedule
from src.anatomy.deal import Deal, load_deal
from src.common.style import ACCENT, BG, INK, INK_MUTED, WARM_GRAY, apply_theme, save_figure


def build_warehouse_ramp_chart(deal: Deal, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir or config.FIGURES_ANATOMY_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = build_warehouse_schedule(deal)
    w = config.ANATOMY_WAREHOUSE

    apply_theme()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.6), facecolor=BG, gridspec_kw={"width_ratios": [1.5, 1]})

    ax1.stackplot(df["quarter"], df["warehouse_debt_drawn"] / 1e6, df["equity_at_risk"] / 1e6,
                  colors=[WARM_GRAY[2], ACCENT], labels=["Warehouse debt", "At-risk equity capital"])
    ax1.axvline(w["takeout_quarter"], color=INK, lw=1.2, linestyle="--")
    ax1.annotate("Closing: CLO takes out\nthe warehouse facility", xy=(w["takeout_quarter"], df["cumulative_par"].max() / 1e6),
                 xytext=(-90, -10), textcoords="offset points", fontsize=8, color=INK,
                 arrowprops=dict(arrowstyle="-", color=INK_MUTED, lw=0.8))
    ax1.set_xlabel("Quarter (relative to closing)")
    ax1.set_ylabel("$ millions")
    ax1.set_title("Ramping the portfolio: debt vs. at-risk equity capital", fontsize=10, fontweight="bold",
                   color=INK, loc="left")
    ax1.legend(loc="upper left", frameon=False, fontsize=8.5)

    ax2.plot(df["quarter"], df["cumulative_net_carry"] / 1e6, color=ACCENT, marker="o", markersize=4)
    ax2.axhline(0, color=INK_MUTED, lw=0.8)
    ax2.set_xlabel("Quarter (relative to closing)")
    ax2.set_ylabel("$ millions")
    ax2.set_title("Cumulative carry earned by warehouse equity", fontsize=10, fontweight="bold", color=INK, loc="left")
    for spine in ("top", "right"):
        ax1.spines[spine].set_visible(False)
        ax2.spines[spine].set_visible(False)

    peak_equity = df.attrs["max_equity_at_risk"]
    clo_equity = df.attrs["clo_equity_size"]
    pct = df.attrs["equity_at_risk_pct_of_clo_equity"]
    total_carry = df.attrs["total_ramp_carry_to_equity"]

    png, svg = save_figure(
        fig, "warehouse_ramp",
        headline="Before the CLO exists, a warehouse facility ramps the portfolio.",
        subtitle=f"Peak at-risk warehouse equity of \\${peak_equity/1e6:.1f}mm ({pct:.0f}% of the \\${clo_equity/1e6:.1f}mm "
                 f"CLO equity tranche) earns \\${total_carry/1e6:.1f}mm of carry before closing, then largely rolls "
                 "into that same equity tranche.",
        source=f"structure illustrative, parameters adapted from {deal.citation.get('deal_name', '')}, public offering circular",
        notes="TO-VERIFY: warehouse lending terms (advance rate, financing spread, ramp shape) are private and never "
              "disclosed in a public offering circular — every figure here is a market-standard convention.",
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
