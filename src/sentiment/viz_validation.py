"""Scorer-agreement exhibit (methods appendix, Section 6 v2): lexicon vs.
LLM-rubric alarm scores on the same hand-scored sample of CLO-mentioning
sections. Methodological honesty as a slide asset, not a footnote.
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, INK, WARM_GRAY, apply_theme, categorical_color, save_figure

logger = logging.getLogger("clo_atlas.sentiment.viz_validation")

COMPARISON_PATH = config.FINAL_DIR / "scorer_validation_comparison.parquet"


def viz_scorer_agreement():
    apply_theme()
    df = read_parquet(COMPARISON_PATH)
    if df.empty:
        logger.warning("no scorer-validation data; skipping viz_scorer_agreement")
        return None

    fig, ax = plt.subplots(figsize=(7, 6))
    institutions = sorted(df["institution"].unique())
    for i, inst in enumerate(institutions):
        sub = df[df["institution"] == inst]
        ax.scatter(sub["lexicon_alarm_proxy"], sub["llm_alarm"], color=categorical_color(i),
                   s=90, alpha=0.85, label=inst, edgecolor="white", linewidth=0.6)

    lims = [0, max(df["lexicon_alarm_proxy"].max(), df["llm_alarm"].max()) * 1.1]
    ax.plot(lims, lims, color=WARM_GRAY[2], linestyle="--", linewidth=1, zorder=0, label="perfect agreement")
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_xlabel("Lexicon alarm proxy (vulnerability + LM negative rate, rescaled)")
    ax.set_ylabel("LLM rubric alarm (0-5)")
    ax.legend(loc="upper left", fontsize=8.5, frameon=False)

    corr = df[["lexicon_alarm_proxy", "llm_alarm"]].corr().iloc[0, 1]
    png, svg = save_figure(
        fig, "viz_scorer_agreement",
        headline=f"Two independent scorers agree directionally (r={corr:.2f}) but not on every section.",
        subtitle=f"Lexicon-based vs. LLM-rubric alarm score, {len(df)} hand-scored CLO-mentioning sections "
                 "(a deliberately spread sample, not the full corpus — see docs/sources.md).",
        source="clo-atlas, scored against a fixed rubric per src.sentiment.scoring.LLM_RUBRIC_PROMPT",
        notes="Sample selected as the 3 highest- and 2 lowest-vulnerability-rate sections per institution, not randomly — "
              "chosen to stress-test agreement at the extremes where it matters most.",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_scorer_agreement()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
