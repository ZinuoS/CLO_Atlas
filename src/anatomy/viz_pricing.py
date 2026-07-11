"""Pricing anatomy: the capital structure (subordination + spread by
rating), WAL sensitivity across scenarios, and the excess-spread bridge
from portfolio yield down to what equity actually keeps.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import config
from src.anatomy.analysis_arb import build_excess_spread_bridge, simulated_base_case_equity_yield_pct
from src.anatomy.analysis_pricing import build_capital_structure_table, build_wal_sensitivity_table
from src.anatomy.deal import Deal, load_deal
from src.anatomy.engine import TRANCHE_ORDER
from src.common.style import ACCENT, BG, INK, INK_MUTED, WARM_GRAY, apply_theme, categorical_color, save_figure


def build_capital_structure_chart(deal: Deal, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir or config.FIGURES_ANATOMY_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = build_capital_structure_table(deal)

    apply_theme()
    fig, ax = plt.subplots(figsize=(11, 4.4), facecolor=BG)
    colors = [WARM_GRAY[3], WARM_GRAY[2], WARM_GRAY[1], WARM_GRAY[0], "#9A5B5B", ACCENT]
    left = 0.0
    for (_, row), color in zip(df.iterrows(), colors):
        width = row["detachment_pct"] - row["attachment_pct"]
        ax.barh(0, width, left=left, color=color, edgecolor=BG, linewidth=1.5, height=0.6)
        label_color = BG if color in (WARM_GRAY[0], "#9A5B5B", ACCENT) else INK
        spread = f"+{row['spread_bps']:.0f}bps" if row["spread_bps"] == row["spread_bps"] else "residual"
        fontsize = 8 if width > 8 else 6.4
        ax.text(left + width / 2, 0, f"{row['name']}\n{row['rating'] or ''}\n{spread}", ha="center", va="center",
                fontsize=fontsize, color=label_color)
        left += width
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.6, 0.6)
    ax.set_xlabel("% of capital structure (attachment from the bottom)")
    ax.get_yaxis().set_visible(False)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)

    png, svg = save_figure(
        fig, "pricing_capital_structure",
        headline="The capital structure: who's protected, and what they're paid for it.",
        subtitle="Subordination (left edge) is how much of the pool has to lose value before that class takes a loss.",
        source=f"structure illustrative, parameters adapted from {deal.citation.get('deal_name', '')}, public offering circular",
        out_dir=out_dir,
    )
    return png


def build_wal_sensitivity_chart(deal: Deal, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir or config.FIGURES_ANATOMY_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = build_wal_sensitivity_table(deal)
    scenario_labels = {"base": "Base", "covid_shock": "COVID shock", "severe_recession": "Severe recession",
                        "post_reinvestment_amortization": "Post-reinvestment amortization"}
    scenarios = list(scenario_labels)

    apply_theme()
    fig, ax = plt.subplots(figsize=(11, 5), facecolor=BG)
    x = np.arange(len(TRANCHE_ORDER))
    n = len(scenarios)
    bar_w = 0.8 / n
    for i, key in enumerate(scenarios):
        vals = [df[(df.scenario == key) & (df.tranche == t)]["wal_years"].iloc[0] for t in TRANCHE_ORDER]
        ax.bar(x + i * bar_w - 0.4 + bar_w / 2, vals, width=bar_w, color=categorical_color(i), label=scenario_labels[key])
    ax.set_xticks(x)
    ax.set_xticklabels(TRANCHE_ORDER)
    ax.set_ylabel("Weighted-average life (years)")
    ax.legend(loc="upper left", frameon=False, fontsize=8.5)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    png, svg = save_figure(
        fig, "pricing_wal_sensitivity",
        headline="How each tranche's life changes under stress.",
        subtitle="WAL is computed from this project's own simulated principal cash flows; a value near the full "
                 "13-year horizon means that class received essentially no principal within the modeled life "
                 "(sequential paydown from the top never reached it in time) — not a data gap.",
        source=f"structure illustrative, parameters adapted from {deal.citation.get('deal_name', '')}, public offering circular",
        out_dir=out_dir,
    )
    return png


def build_excess_spread_chart(deal: Deal, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir or config.FIGURES_ANATOMY_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = build_excess_spread_bridge(deal)
    simulated_yield = simulated_base_case_equity_yield_pct(deal)

    apply_theme()
    fig, ax = plt.subplots(figsize=(11, 5), facecolor=BG)
    cumulative = 0.0
    for i, row in df.iterrows():
        is_total = row["step"].startswith("=")
        bottom = 0.0 if is_total else min(cumulative, cumulative + row["bps"])
        height = row["bps"] if is_total else abs(row["bps"])
        color = ACCENT if is_total else (WARM_GRAY[2] if row["bps"] >= 0 else WARM_GRAY[0])
        ax.bar(i, height, bottom=bottom, color=color, width=0.6)
        if not is_total:
            cumulative += row["bps"]
        va = "bottom" if row["bps"] >= 0 else "top"
        ax.text(i, bottom + height + (2 if row["bps"] >= 0 else -2), f"{row['bps']:+.0f}", ha="center",
                va=va, fontsize=8, color=INK)
    import textwrap
    wrapped_labels = ["\n".join(textwrap.wrap(s, width=14)) for s in df["step"]]
    ax.set_xticks(range(len(df)))
    ax.set_xticklabels(wrapped_labels, fontsize=7.2)
    ax.set_ylabel("bps of collateral par")
    ax.axhline(0, color=INK_MUTED, lw=0.8)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    png, svg = save_figure(
        fig, "pricing_excess_spread_bridge",
        headline="The CLO arbitrage: where portfolio yield actually goes.",
        subtitle=f"Analytical steady-state bridge implies a {df.attrs['implied_equity_yield_pct']:.1f}% equity yield; "
                 f"the engine's simulated base-case average is {simulated_yield:.1f}% — the gap is the amortizing, "
                 "sequential-paydown path a static bridge can't capture.",
        source=f"structure illustrative, parameters adapted from {deal.citation.get('deal_name', '')}, public offering circular",
        notes="TO-VERIFY: expected-loss and fee-basis conventions in the bridge are this project's simplifying "
              "assumptions, not circular figures.",
        out_dir=out_dir,
    )
    return png


def main():
    deal = load_deal()
    print(f"wrote {build_capital_structure_chart(deal)}")
    print(f"wrote {build_wal_sensitivity_chart(deal)}")
    print(f"wrote {build_excess_spread_chart(deal)}")


if __name__ == "__main__":
    main()
