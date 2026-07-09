""""One loan, five prices" (Section 3) — the signature exhibit: one row per
crowded loan, one dot per holder's mark, range bar behind, worst rows
annotated.

Today's coverage is 2+ filers per issuer (mission brief's >=3 bar isn't met
yet — see analysis_mark_dispersion.py's docstring for why), so this reads
"one loan, several prices" honestly rather than claiming five.
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, WARM_GRAY, apply_theme, save_figure

logger = logging.getLogger("clo_atlas.edgar.viz_dispersion")

MARKS_PATH = config.FINAL_DIR / "edgar_crowded_marks.parquet"
SUMMARY_PATH = config.FINAL_DIR / "edgar_mark_dispersion_summary.parquet"


def viz_one_loan_several_prices(top_n: int = 15):
    apply_theme()
    marks = read_parquet(MARKS_PATH)
    summary = read_parquet(SUMMARY_PATH)
    if marks.empty or summary.empty:
        logger.warning("no crowded-mark data cached; skipping viz_one_loan_several_prices")
        return None

    top = summary.nlargest(top_n, "spread")
    top_keys = set(zip(top["canonical_name"], top["period"]))
    plot_rows = marks[marks.apply(lambda r: (r["canonical_name"], r["period"]) in top_keys, axis=1)].copy()
    plot_rows["row_label"] = plot_rows["canonical_name"].str.slice(0, 28) + " · " + plot_rows["period"].astype(str)
    order = top.assign(row_label=top["canonical_name"].str.slice(0, 28) + " · " + top["period"].astype(str))["row_label"].tolist()

    fig, ax = plt.subplots(figsize=(9, 7))
    y_pos = {label: i for i, label in enumerate(reversed(order))}
    for _, row in top.iterrows():
        label = row["canonical_name"][:28] + " · " + str(row["period"])
        y = y_pos[label]
        ax.plot([row["min_price"], row["max_price"]], [y, y], color=WARM_GRAY[1], linewidth=3, zorder=1, solid_capstyle="round")
    for _, row in plot_rows.iterrows():
        y = y_pos[row["row_label"]]
        ax.scatter(row["price"], y, color=ACCENT, s=50, zorder=2, edgecolor="white", linewidth=0.6)

    ax.set_yticks(list(y_pos.values()))
    ax.set_yticklabels(list(y_pos.keys()), fontsize=8.5)
    ax.set_xlabel("Mark (par = 100)")
    fig.subplots_adjust(left=0.38)

    png, svg = save_figure(
        fig, "viz_one_loan_several_prices",
        headline="The same company's debt gets marked at wildly different prices by different holders.",
        subtitle=f"The {top_n} widest cross-filer mark disagreements found so far: each dot is one BDC/fund's "
                  "mark on the same issuer in the same reporting period; the bar spans the full range. "
                  "Coverage today is 2+ filers per name (5/8 tracked BDCs parsed successfully this run).",
        source="clo-atlas, from SEC EDGAR BDC Schedules of Investment and N-PORT-P filings, entity-resolved",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_one_loan_several_prices()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
