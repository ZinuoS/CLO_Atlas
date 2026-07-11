"""Coverage-test dashboards: OC ratio per test level vs. its trigger
threshold over the life of the deal, one chart per scenario. Breach
quarters get an accent marker so a reader can see exactly when and how
long a test failed without reading the click-through frames one by one.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

import config
from src.anatomy.deal import Deal, load_deal
from src.anatomy.scenarios import build_scenarios, run_scenario
from src.common.style import apply_theme, categorical_color, direct_label, save_figure

TEST_LEVELS = ("AA", "A", "BBB", "BB")


def build_coverage_dashboard(deal: Deal, scenario_key: str, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir or config.FIGURES_ANATOMY_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    scenarios = build_scenarios(deal)
    scenario = scenarios[scenario_key]
    df = run_scenario(deal, scenario)

    apply_theme()
    fig, ax = plt.subplots(figsize=(11, 6), facecolor="#FFFFFF")

    for i, level in enumerate(TEST_LEVELS):
        color = categorical_color(i)
        ax.plot(df["period"], df[f"oc_ratio_{level}"], color=color, lw=1.8, zorder=3)
        trigger = deal.oc_triggers_pct[level]
        ax.axhline(trigger, color=color, lw=1.0, linestyle="--", alpha=0.6, zorder=2)
        breach = ~df[f"oc_pass_{level}"]
        if breach.any():
            ax.scatter(df.loc[breach, "period"], df.loc[breach, f"oc_ratio_{level}"],
                       color="#D0021B", s=18, zorder=4, marker="o")
        direct_label(ax, df["period"].iloc[-1], df[f"oc_ratio_{level}"].iloc[-1], f"{level} OC", color=color)

    trigger_lines = "   ".join(f"{level} trigger {deal.oc_triggers_pct[level]:.1f}%" for level in TEST_LEVELS)
    ax.text(0.01, 0.02, trigger_lines, transform=ax.transAxes, fontsize=8, color="#5C5652", ha="left", va="bottom")

    ax.set_xlabel("Quarter")
    ax.set_ylabel("OC ratio (%)")
    # A senior class's OC ratio mathematically diverges toward infinity as
    # its own balance (the denominator) pays down to zero — real behavior,
    # not a data error, but left unclipped it swamps every other level on a
    # linear axis. The view is capped; the underlying data is not.
    y_cap = 260.0
    ax.set_ylim(0, y_cap)

    png, svg = save_figure(
        fig, f"waterfall_tests_{scenario_key}",
        headline=f"Coverage tests over the deal's life — {scenario_key.replace('_', ' ')}.",
        subtitle=scenario.thesis + " Red dots mark quarters where that level's OC (or paired IC) test fails; "
                                   "dashed lines are each level's trigger.",
        source=f"structure illustrative, parameters adapted from {deal.citation.get('deal_name', '')}, public offering circular",
        notes=f"Y-axis capped at {y_cap:.0f}% for readability — a level's true OC ratio rises without bound as its "
              "own tranche (the ratio's denominator) fully pays down; it is never actually clipped or capped in the model.",
        out_dir=out_dir,
    )
    return png


ALL_SCENARIO_KEYS = ("base", "covid_shock", "severe_recession", "post_reinvestment_amortization",
                     "rate_shock_up", "rate_shock_down")


def main():
    for key, path in run().items():
        print(f"{key}: wrote {path}")


def run(deal: Deal | None = None) -> dict[str, Path]:
    deal = deal or load_deal()
    return {key: build_coverage_dashboard(deal, key) for key in ALL_SCENARIO_KEYS}


if __name__ == "__main__":
    main()
