"""Single-moment waterfall explainers — the "how this works" reference
diagrams, as distinct from `viz_waterfall_dynamics.py`'s scenario-driven
click-through/ghost/matrix/stream charts. Two canonical moments are
rendered because the principal waterfall behaves fundamentally differently
in each regime and both deserve their own clearly labeled explainer: a
reinvestment-period quarter (principal recycles into new collateral) and a
post-reinvestment quarter (principal pays down the stack sequentially).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import FancyArrowPatch

import config
from src.anatomy.deal import Deal, load_deal
from src.anatomy.engine import TRANCHE_ORDER
from src.anatomy.scenarios import build_scenarios, run_scenario
from src.common.style import ACCENT, BG, INK, INK_MUTED, WARM_GRAY, apply_theme
from src.anatomy.viz_waterfall_dynamics import (
    FONT_NODE_AMOUNT, FONT_NODE_LABEL, NODE_H, NODE_W, NODE_X0, NODES, _draw_box, _node_amount, _period_label,
)

FIGSIZE_IN = (12.8, 7.2)
DPI = 150

PRINCIPAL_X0, PRINCIPAL_W = 8.3, 1.7
PRINCIPAL_NODE_H = 0.62


def _principal_amount(row: pd.Series, name: str) -> float:
    val = row.get(f"stop_principal_{name}", 0.0)
    return 0.0 if pd.isna(val) else float(val)


def render_single_moment(deal: Deal, row: pd.Series, mode_label: str) -> plt.Figure:
    apply_theme()
    fig = plt.figure(figsize=FIGSIZE_IN, dpi=DPI, facecolor=BG)
    ax = fig.add_axes((0.045, 0.14, 0.90, 0.72))
    ax.set_xlim(0, 12.4)
    ax.set_ylim(1.6, 13.4)
    ax.axis("off")

    # Left/center: interest waterfall (identical node set to the dynamics module).
    for key, label, y, test_level in NODES:
        amount = _node_amount(row, key)
        passing = bool(row.get(f"oc_pass_{test_level}", True)) if test_level else True
        fill = "#F6C6CC" if not passing else (WARM_GRAY[3] if amount > 0 else "#F5F3EF")
        _draw_box(ax, NODE_X0, y, NODE_W, NODE_H, "", fill)
        ax.text(NODE_X0 + 0.18, y + 0.10, label, ha="left", va="center", fontsize=FONT_NODE_LABEL, color=INK)
        ax.text(NODE_X0 + NODE_W - 0.18, y - 0.14, f"${amount:,.0f}", ha="right", va="center",
                fontsize=FONT_NODE_AMOUNT, color=INK_MUTED, fontweight="medium")
    ys = [y for _, _, y, _ in NODES]
    for y_top, y_bot in zip(ys[:-1], ys[1:]):
        ax.add_patch(FancyArrowPatch((NODE_X0 + NODE_W / 2, y_top - NODE_H / 2 - 0.01),
                                      (NODE_X0 + NODE_W / 2, y_bot + NODE_H / 2 + 0.01),
                                      arrowstyle="-|>", mutation_scale=8, color=INK_MUTED, lw=0.9, zorder=1))
    ax.text(NODE_X0, 13.15, "INTEREST WATERFALL", fontsize=9, color=INK_MUTED, fontweight="bold", ha="left")

    # Right: principal waterfall — the two regimes render completely
    # differently, which is the point of this pair of explainers.
    ax.text(PRINCIPAL_X0, 13.15, "PRINCIPAL WATERFALL", fontsize=9, color=INK_MUTED, fontweight="bold", ha="left")
    reinvesting = bool(row["reinvesting"])
    if reinvesting:
        y = 11.0
        _draw_box(ax, PRINCIPAL_X0, y, PRINCIPAL_W, 1.6, "", WARM_GRAY[3])
        ax.text(PRINCIPAL_X0 + PRINCIPAL_W / 2, y + 0.35, "Prepayments + recoveries",
                ha="center", va="center", fontsize=8.4, color=INK)
        ax.text(PRINCIPAL_X0 + PRINCIPAL_W / 2, y, f"${_principal_amount(row, 'principal_reinvested'):,.0f}",
                ha="center", va="center", fontsize=10, color=INK, fontweight="bold")
        ax.text(PRINCIPAL_X0 + PRINCIPAL_W / 2, y - 0.35, "reinvested in new collateral\n(all coverage tests pass)",
                ha="center", va="center", fontsize=7.6, color=INK_MUTED)
        ax.add_patch(FancyArrowPatch((PRINCIPAL_X0 + PRINCIPAL_W / 2, y - 0.85), (PRINCIPAL_X0 + PRINCIPAL_W / 2, y - 1.5),
                                      arrowstyle="-|>", mutation_scale=10, color=INK_MUTED, lw=1.1))
        ax.text(PRINCIPAL_X0 + PRINCIPAL_W / 2, y - 1.9, "performing collateral pool\n(par grows or holds steady)",
                ha="center", va="center", fontsize=7.8, color=INK_MUTED, style="italic")
    else:
        pay_y = {"AAA": 11.0, "AA": 9.6, "A": 8.2, "BBB": 6.8, "BB": 5.4, "equity": 4.0}
        ax.text(PRINCIPAL_X0 + PRINCIPAL_W / 2, 12.0, "Sequential paydown\n(reinvestment ended or a test is failing)",
                ha="center", va="center", fontsize=7.8, color=INK_MUTED, style="italic")
        prev_y = 12.4
        for name in list(TRANCHE_ORDER):
            y = pay_y[name]
            amt = _principal_amount(row, f"{name}_principal" if name != "equity" else "equity_residual_principal")
            fill = ACCENT if amt > 0 else "#F5F3EF"
            _draw_box(ax, PRINCIPAL_X0, y, PRINCIPAL_W, PRINCIPAL_NODE_H, "", fill,
                      text_color=(BG if amt > 0 else INK_MUTED))
            label = "Equity (residual)" if name == "equity" else f"{name} principal"
            ax.text(PRINCIPAL_X0 + PRINCIPAL_W / 2, y + 0.14, label, ha="center", va="center", fontsize=8,
                    color=(BG if amt > 0 else INK_MUTED))
            ax.text(PRINCIPAL_X0 + PRINCIPAL_W / 2, y - 0.16, f"${amt:,.0f}", ha="center", va="center", fontsize=8.4,
                    color=(BG if amt > 0 else INK_MUTED), fontweight="bold")
            ax.add_patch(FancyArrowPatch((PRINCIPAL_X0 + PRINCIPAL_W / 2, prev_y - 0.35),
                                          (PRINCIPAL_X0 + PRINCIPAL_W / 2, y + PRINCIPAL_NODE_H / 2 + 0.02),
                                          arrowstyle="-|>", mutation_scale=8, color=INK_MUTED, lw=0.9))
            prev_y = y

    period = int(row["period"])
    fig.text(0.045, 0.955, f"How the waterfall works: {mode_label}.", fontsize=15, fontweight="bold", color=INK, ha="left", va="top")
    fig.text(0.045, 0.905, f"{_period_label(deal, period)}  ·  CDR {row['cdr_pct']:.1f}%  ·  CPR {row['cpr_pct']:.1f}%  ·  "
                          f"recovery {row['recovery_rate_pct']:.0f}%  ·  SOFR {row['sofr_pct']:.2f}%  ·  "
                          f"base case", fontsize=10, color=INK_MUTED, ha="left", va="top")
    source = deal.citation.get("deal_name", "")
    fig.text(0.045, 0.045, f"SOURCE: STRUCTURE ILLUSTRATIVE, PARAMETERS ADAPTED FROM {source.upper()}, "
                          "PUBLIC OFFERING CIRCULAR", fontsize=7.5, color=INK_MUTED, ha="left", va="bottom")
    fig.text(0.94, 0.045, "Credit: Ashley Shi", fontsize=7.5, color=INK_MUTED, ha="right", va="bottom")
    fig.text(0.045, 0.02, "Model simplifications: single simplified BSL structure (2 collapsed sub-classes per "
                          "original class, non-economic overlay note dropped); no explicit EOD/acceleration path.",
             fontsize=6.4, color=INK_MUTED, ha="left", va="bottom", style="italic")
    return fig


def build_single_moment_explainers(deal: Deal, out_dir: Path | None = None) -> list[Path]:
    out_dir = Path(out_dir or config.FIGURES_ANATOMY_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    scenarios = build_scenarios(deal)
    df = run_scenario(deal, scenarios["base"])

    reinvest_row = df[df["reinvesting"]].iloc[len(df[df["reinvesting"]]) // 2]
    amort_row = df[~df["reinvesting"]].iloc[0] if (~df["reinvesting"]).any() else df.iloc[-1]

    paths = []
    for row, mode_label, fname in (
        (reinvest_row, "a reinvestment-period quarter", "waterfall_moment_reinvesting.png"),
        (amort_row, "a post-reinvestment quarter", "waterfall_moment_amortizing.png"),
    ):
        fig = render_single_moment(deal, row, mode_label)
        path = out_dir / fname
        fig.savefig(path, dpi=DPI, facecolor=BG)
        plt.close(fig)
        paths.append(path)
    return paths


def main():
    deal = load_deal()
    for p in build_single_moment_explainers(deal):
        print(f"wrote {p}")


if __name__ == "__main__":
    main()
