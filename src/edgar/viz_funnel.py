"""The entity-resolution funnel (Section 3) — a methods slide that doubles
as an engineering flex per the mission brief: exact / alias / fuzzy-auto /
fuzzy-review / unresolved, from analysis_resolution.py's real run against
BDC SOI + bank-loan-fund NPORT issuer names.
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, WARM_GRAY, apply_theme, save_figure

logger = logging.getLogger("clo_atlas.edgar.viz_funnel")

FUNNEL_PATH = config.FINAL_DIR / "edgar_resolution_funnel.parquet"

_STAGE_ORDER = ["exact", "alias", "fuzzy_auto", "fuzzy_review", "unresolved"]
_STAGE_LABELS = {
    "exact": "Exact\nmatch", "alias": "Alias\ntable", "fuzzy_auto": "Fuzzy\nauto (≥92)",
    "fuzzy_review": "Fuzzy\nreview (80-92)", "unresolved": "Unresolved\n(new entity)",
}


def viz_resolution_funnel():
    apply_theme()
    df = read_parquet(FUNNEL_PATH)
    if df.empty:
        logger.warning("no resolution funnel data cached; skipping viz_resolution_funnel")
        return None
    row = df.iloc[0]
    values = [row[s] for s in _STAGE_ORDER]
    labels = [_STAGE_LABELS[s] for s in _STAGE_ORDER]
    colors = [ACCENT if s == "exact" else WARM_GRAY[1] for s in _STAGE_ORDER]

    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    bars = ax.bar(labels, values, color=colors)
    for bar, v in zip(bars, values):
        ax.annotate(f"{int(v):,}", xy=(bar.get_x() + bar.get_width() / 2, v), xytext=(0, 4),
                    textcoords="offset points", ha="center", fontsize=9)
    ax.set_ylabel("Issuer-name mentions")

    png, svg = save_figure(
        fig, "viz_resolution_funnel",
        headline=f"{row['match_rate']*100:.0f}% of issuer names resolve automatically across sources.",
        subtitle=f"Match cascade for {int(row['total']):,} issuer-name mentions across BDC SOI and bank-loan-fund "
                  "N-PORT filings: normalize -> exact -> alias -> fuzzy (rapidfuzz) -> unresolved becomes a new entity.",
        source="clo-atlas, common/entity.py resolution cascade",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_resolution_funnel()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
