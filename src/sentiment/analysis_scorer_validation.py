"""Methodological honesty module: lexicon-vs-LLM scorer agreement (Section 6 v2).

Two independent scorers per CLO-mentioning section: the deterministic
lexicon score (LM negative rate + vulnerability-lexicon rate) from
`scoring.py`, and a fixed-rubric LLM judgment (alarm 0-5, stance, evidence
quote) cached in `data/_llm_cache/sentiment_rubric_*.json` per
`scoring.llm_rubric_score_cached`.

Coverage discipline: only sections with a cached LLM score are included in
the comparison (currently a hand-scored, deliberately spread sample — not
the full ~150-section corpus; see `docs/sources.md` for exactly how the
sample was chosen and scored). The denominator is reported on every chart
this module feeds, per the project's coverage-discipline rule.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet
from src.sentiment.scoring import llm_rubric_score_cached

logger = logging.getLogger("clo_atlas.sentiment.analysis_scorer_validation")

SECTION_SCORES_PATH = config.FINAL_DIR / "alarm_v2_section_scores.parquet"

OUT_COMPARISON = config.FINAL_DIR / "scorer_validation_comparison.parquet"
OUT_DISAGREEMENT = config.FINAL_DIR / "scorer_validation_disagreement.parquet"

# A lexicon score above this (on its own 0-1-ish rate scale, rescaled to 0-5
# below for comparability with the LLM's 0-5 alarm scale) counts as
# lexicon-side "high alarm" for the disagreement table.
_LEXICON_RESCALE = 100  # vulnerability_rate + lm_negative_rate are token-level rates (~0-0.05); *100 lands near 0-5


def scored_comparison() -> pd.DataFrame:
    if not SECTION_SCORES_PATH.exists():
        logger.warning("no section-level scores cached; run analysis_alarm_v2.py first")
        return pd.DataFrame(columns=["institution", "date", "section", "lexicon_alarm_proxy", "llm_alarm", "llm_stance"])
    sections = read_parquet(SECTION_SCORES_PATH)

    rows = []
    for _, row in sections.iterrows():
        try:
            llm = llm_rubric_score_cached(row["section"])
        except NotImplementedError:
            continue
        lexicon_proxy = ((row["vulnerability_rate"] or 0) + (row["lm_negative_rate"] or 0)) * _LEXICON_RESCALE
        rows.append({
            "institution": row["institution"], "date": row["date"], "section": row["section"],
            "lexicon_alarm_proxy": lexicon_proxy, "llm_alarm": llm["alarm"], "llm_stance": llm["stance"],
            "llm_evidence_quote": llm.get("evidence_quote", ""),
        })
    out = pd.DataFrame(rows)
    n_total = len(sections)
    logger.info("scorer validation: %d/%d sections have a cached LLM score (%.0f%% coverage)",
                len(out), n_total, 100 * len(out) / n_total if n_total else 0)
    return out


def disagreement_table(comparison: pd.DataFrame, threshold: float = 2.0) -> pd.DataFrame:
    """Sections where the two scorers disagree by more than `threshold` on
    a comparable 0-5-ish scale — the honest cases where lexicon and LLM
    scoring diverge, not swept into a summary correlation."""
    if comparison.empty:
        return pd.DataFrame(columns=["institution", "date", "lexicon_alarm_proxy", "llm_alarm", "gap"])
    df = comparison.copy()
    df["gap"] = (df["lexicon_alarm_proxy"] - df["llm_alarm"]).abs()
    return df[df["gap"] >= threshold].sort_values("gap", ascending=False)


def run() -> dict[str, pd.DataFrame]:
    comparison = scored_comparison()
    write_parquet(comparison, OUT_COMPARISON, Provenance(
        parser="src.sentiment.analysis_scorer_validation.scored_comparison", source_urls=[],
        notes=f"{len(comparison)} sections with a cached LLM rubric score, hand-scored sample (see docs/sources.md), "
              "not the full corpus — coverage stated explicitly.",
    ))

    disagreement = disagreement_table(comparison)
    write_parquet(disagreement, OUT_DISAGREEMENT, Provenance(
        parser="src.sentiment.analysis_scorer_validation.disagreement_table", source_urls=[]))

    corr = comparison[["lexicon_alarm_proxy", "llm_alarm"]].corr().iloc[0, 1] if len(comparison) > 2 else None
    logger.info("comparison=%d sections, disagreement=%d sections, correlation=%s",
                len(comparison), len(disagreement), f"{corr:.2f}" if corr is not None else "n/a (too few points)")
    return {"comparison": comparison, "disagreement": disagreement}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
