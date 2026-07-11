"""Domain sentiment scoring for CLO-mentioning text (Section 6 v2).

Replaces the original VADER-first, multiplicative approach
(`analysis_alarm_index.py`) for three reasons discovered by inspecting real
output, not just the resulting chart:

1. VADER is tuned for social-media valence and rarely fires on
   professionally neutral regulator prose — most CLO-mentioning sections
   score ~0.0 regardless of content.
2. The original index (`mentions x max(-vader, 0)`) is multiplicative: a
   report with heavy CLO coverage but non-negative measured tone gets
   zeroed out, which is wrong — coverage intensity is itself informative.
3. Semiannual/quarterly reports give ~2-4 observations/year per
   institution; sparsity needs to be visible on the chart, not hidden.

This module scores each CLO-mentioning sentence-window on three DOMAIN
dimensions instead: Loughran-McDonald negative rate, LM uncertainty rate,
and a hand-curated vulnerability-lexicon hit rate (config.VULNERABILITY_STEMS)
— regulator alarm lives in "contagion"/"fire sale"/"amplification", not in
VADER's "good"/"bad". A second, independent scorer (a fixed-prompt LLM
rubric, temperature 0, cached by input hash) is included for cross-
validation — see `analysis_scorer_validation.py` for the disagreement
analysis this is built to support.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re

import pandas as pd

import config
from src.common.text import LMLexicon, mention_rate_per_1000, score_lm, score_vulnerability, split_sentences

logger = logging.getLogger("clo_atlas.sentiment.scoring")

_CLO_MENTION_PATTERN = re.compile(r"\bclos?\b", re.IGNORECASE)
_SENTENCE_WINDOW = 1  # sentences of context on each side of a CLO mention

LLM_RUBRIC_CACHE_DIR = config.LLM_CACHE_DIR
LLM_RUBRIC_PROMPT = """You are scoring a short excerpt from a financial-stability or regulatory \
document for its stance on collateralized loan obligations (CLOs). Read the excerpt and return \
ONLY a JSON object with these keys:
  "alarm": integer 0-5 (0 = no concern expressed, 5 = severe systemic-risk alarm)
  "stance": one of "risk-flagging", "neutral-monitoring", "reassuring"
  "evidence_quote": the single most representative quote from the excerpt, <=15 words
Temperature 0. No prose outside the JSON object.

EXCERPT:
{excerpt}
"""


def try_load_lm() -> LMLexicon | None:
    try:
        return LMLexicon.load()
    except FileNotFoundError as exc:
        logger.warning("LM lexicon unavailable (%s); domain scoring will use vulnerability-lexicon rate only.", exc)
        return None


def extract_clo_sections(text: str) -> list[str]:
    """Sentence-window extraction around each CLO mention (paragraph breaks
    aren't reliable in pdfplumber output for these PDFs — see the original
    module's docstring for why sentence windows are used instead)."""
    sentences = split_sentences(text)
    mention_idx = [i for i, s in enumerate(sentences) if _CLO_MENTION_PATTERN.search(s)]
    windows = []
    for i in mention_idx:
        lo, hi = max(0, i - _SENTENCE_WINDOW), min(len(sentences), i + _SENTENCE_WINDOW + 1)
        windows.append(" ".join(sentences[lo:hi]))
    return windows


def score_section_domain(section: str, lm: LMLexicon | None = None) -> dict:
    """LM negative/uncertainty rates + vulnerability-lexicon rate for one
    CLO-mentioning section. Returns raw rates, not yet z-scored (z-scoring
    needs the full report-level panel — see `additive_alarm_index`)."""
    out = {"vulnerability_rate": score_vulnerability(section)}
    if lm is not None:
        lm_score = score_lm(section, lm)
        out["lm_negative_rate"] = lm_score.n_negative / lm_score.n_tokens if lm_score.n_tokens else 0.0
        out["lm_uncertainty_rate"] = lm_score.uncertainty_rate
        out["lm_net_sentiment"] = lm_score.net_sentiment
    else:
        out["lm_negative_rate"] = None
        out["lm_uncertainty_rate"] = None
        out["lm_net_sentiment"] = None
    return out


def score_document(text: str, institution: str, date) -> pd.DataFrame:
    """All CLO-mentioning sections in one document, domain-scored."""
    lm = try_load_lm()
    sections = extract_clo_sections(text)
    rows = []
    for section in sections:
        row = {"institution": institution, "date": date, "section": section}
        row.update(score_section_domain(section, lm))
        rows.append(row)
    return pd.DataFrame(rows)


def institution_zscore(df: pd.DataFrame, value_col: str, group_col: str = "institution") -> pd.Series:
    """Z-score within group (institution fixed effects) — the IMF/BIS-style
    institution is structurally gloomier or terser than the Fed in ways that
    have nothing to do with CLO-specific alarm, so raw cross-institution
    comparison would confound style with signal."""
    def _z(s: pd.Series) -> pd.Series:
        std = s.std(ddof=0)
        return (s - s.mean()) / std if std else pd.Series(0.0, index=s.index)
    return df.groupby(group_col)[value_col].transform(_z)


def additive_alarm_index(report_level: pd.DataFrame) -> pd.DataFrame:
    """Additive alarm index = z(mention_rate) + z(vulnerability_rate) +
    z(lm_negative_rate), each z-scored within institution. Components kept
    as their own columns so a coverage spike without negative tone is
    visible (small-multiples in viz_alarm_v2.py), not summed away."""
    df = report_level.copy()
    for col in ("mentions_per_1000", "vulnerability_rate", "lm_negative_rate"):
        z_col = f"z_{col}"
        if col in df.columns and df[col].notna().any():
            df[z_col] = institution_zscore(df, col)
        else:
            df[z_col] = 0.0
    df["alarm_index_v2"] = df[["z_mentions_per_1000", "z_vulnerability_rate", "z_lm_negative_rate"]].sum(axis=1)
    return df


def coverage_table(reports: pd.DataFrame) -> pd.DataFrame:
    """institution x year -> document count. Required artifact per the
    project's coverage-discipline rule: a headline must state its
    denominator, and this table is that denominator."""
    if reports.empty:
        return pd.DataFrame(columns=["institution", "year", "n_documents"])
    df = reports.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    return df.groupby(["institution", "year"]).size().reset_index(name="n_documents")


# ---------------------------------------------------------------------------
# LLM rubric scorer — second, independent scorer for cross-validation.
# Same documented-stub pattern as src/common/entity.py's llm_tiebreak_cached:
# no model-call wiring or new SDK dependency in this repo; self-caches to
# disk keyed by a hash of the input text, so once a cache entry exists
# (whether backfilled by hand or by a wired-in call) reruns are free and
# deterministic. Every score actually used in this project's charts was
# produced by reading the excerpt and applying the fixed rubric above
# exactly once, then cached — see data/_llm_cache/sentiment_rubric_*.json
# and analysis_scorer_validation.py for which sections were sampled and why.
# ---------------------------------------------------------------------------
def llm_rubric_score_cached(excerpt: str) -> dict:
    key = hashlib.sha256(excerpt.encode()).hexdigest()
    cache_path = LLM_RUBRIC_CACHE_DIR / f"sentiment_rubric_{key}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text())
    raise NotImplementedError(
        f"No cached LLM rubric score for this excerpt (would write to {cache_path}). "
        "This project scores a bounded, documented sample by hand against the fixed "
        "prompt in LLM_RUBRIC_PROMPT rather than wiring a live model API call/new SDK "
        "dependency — see analysis_scorer_validation.py for the sampled set."
    )


def main():
    logging.basicConfig(level=logging.INFO)
    sample = "Vulnerabilities in the CLO market remain elevated, with fire sale risk amplifying stress."
    lm = try_load_lm()
    print(score_section_domain(sample, lm))


if __name__ == "__main__":
    main()
