"""The regulatory alarm index (Section 6) — the centerpiece: per report, CLO
mention count per 1,000 tokens x negativity of CLO-mentioning paragraphs,
per institution and pooled, over time.

Primary scorer is VADER (bundled with the vaderSentiment package, no
download needed), not the Loughran-McDonald financial lexicon the mission
brief specified as primary: the LM master dictionary's download link on its
own site (sraf.nd.edu) is rendered client-side and this project couldn't
resolve it to a scriptable URL in the time available (the dictionary itself
is free for academic use, per the page text — this is a discovery-effort
gap, not a licensing one). `common/text.py`'s `LMLexicon.load()` still works
and is tried first; if `data/_lexicons/lm_master_dictionary.csv` is placed
there manually, this module automatically switches to reporting LM
alongside VADER (matching the mission brief's "report both series and their
disagreement" instruction) rather than needing a code change.
"""
from __future__ import annotations

import logging
import re

import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

import config
from src.common.cache import Provenance, read_parquet, write_parquet
from src.common.text import LMLexicon, mention_rate_per_1000, score_lm, split_sentences

logger = logging.getLogger("clo_atlas.sentiment.analysis_alarm_index")

REPORTS_PATH = config.INTERIM_DIR / "regulator_reports.parquet"
OUT_PARAGRAPH = config.FINAL_DIR / "alarm_index_paragraph_scores.parquet"
OUT_INDEX = config.FINAL_DIR / "alarm_index_by_report.parquet"

_vader = SentimentIntensityAnalyzer()


def _try_load_lm() -> LMLexicon | None:
    try:
        return LMLexicon.load()
    except FileNotFoundError as exc:
        logger.warning("LM lexicon unavailable (%s); scoring with VADER only. "
                        "Place the CSV at %s to also get LM scores.", exc, config.LM_DICTIONARY_PATH)
        return None


_CLO_MENTION_PATTERN = re.compile(r"\bclos?\b", re.IGNORECASE)
_SENTENCE_WINDOW = 1  # sentences of context on each side of a CLO mention


def clo_paragraph_scores() -> pd.DataFrame:
    """Despite the name (kept for the mission brief's "paragraph-level
    scoring" framing), this extracts a small sentence-window around each CLO
    mention rather than splitting on blank lines. pdfplumber's extracted text
    doesn't reliably preserve paragraph breaks for these PDFs (glossaries,
    author bylines, and body text often run together into one multi-page
    blob with no blank line between them) — scoring one of those blobs as a
    unit dilutes any CLO-specific sentiment into whatever incidental
    language surrounds it and reliably drove every VADER score to ~1.0
    regardless of content, discovered by inspecting the actual "paragraphs"
    being scored, not just the resulting chart.
    """
    if not REPORTS_PATH.exists():
        logger.warning("no regulator reports cached; run scrape_regulators.py first")
        return pd.DataFrame(columns=["institution", "date", "paragraph", "vader_compound"])

    reports = read_parquet(REPORTS_PATH)
    lm = _try_load_lm()

    rows = []
    for _, report in reports.iterrows():
        sentences = split_sentences(report["text"])
        mention_idx = [i for i, s in enumerate(sentences) if _CLO_MENTION_PATTERN.search(s)]
        for i in mention_idx:
            lo, hi = max(0, i - _SENTENCE_WINDOW), min(len(sentences), i + _SENTENCE_WINDOW + 1)
            window = " ".join(sentences[lo:hi])
            vader_score = _vader.polarity_scores(window)["compound"]
            row = {"institution": report["institution"], "date": report["date"], "paragraph": window,
                   "vader_compound": vader_score}
            if lm is not None:
                lm_score = score_lm(window, lm)
                row["lm_net_sentiment"] = lm_score.net_sentiment
                row["lm_uncertainty"] = lm_score.uncertainty_rate
            rows.append(row)
    if not rows:
        logger.warning("no CLO mentions found in cached reports")
    return pd.DataFrame(rows)


def alarm_index_by_report(paragraph_scores: pd.DataFrame) -> pd.DataFrame:
    if not REPORTS_PATH.exists():
        return pd.DataFrame(columns=["institution", "date", "mentions_per_1000", "mean_vader", "alarm_index"])
    reports = read_parquet(REPORTS_PATH)

    rows = []
    for _, report in reports.iterrows():
        rate = mention_rate_per_1000(report["text"], ["CLO", "collateralized loan obligation"])
        mentions = rate["CLO"] + rate["collateralized loan obligation"]
        para_subset = paragraph_scores[(paragraph_scores["institution"] == report["institution"]) &
                                         (paragraph_scores["date"] == report["date"])]
        mean_vader = para_subset["vader_compound"].mean() if len(para_subset) else 0.0
        # Alarm = mention intensity x negativity (negative sentiment -> positive alarm).
        alarm = mentions * max(-mean_vader, 0)
        row = {"institution": report["institution"], "date": report["date"],
               "mentions_per_1000": mentions, "mean_vader": mean_vader, "alarm_index": alarm}
        if "lm_net_sentiment" in para_subset.columns and len(para_subset):
            mean_lm = para_subset["lm_net_sentiment"].mean()
            row["mean_lm_net_sentiment"] = mean_lm
            row["alarm_index_lm"] = mentions * max(-mean_lm, 0)
        rows.append(row)
    return pd.DataFrame(rows).sort_values("date")


def run() -> dict[str, pd.DataFrame]:
    paragraphs = clo_paragraph_scores()
    write_parquet(paragraphs, OUT_PARAGRAPH, Provenance(parser="src.sentiment.analysis_alarm_index.clo_paragraph_scores", source_urls=[]))

    index = alarm_index_by_report(paragraphs)
    write_parquet(index, OUT_INDEX, Provenance(
        parser="src.sentiment.analysis_alarm_index.alarm_index_by_report", source_urls=[],
        notes="VADER-scored; LM scores included only if the lexicon CSV was placed manually.",
    ))

    logger.info("paragraph_scores=%d rows, alarm_index=%d reports", len(paragraphs), len(index))
    return {"paragraphs": paragraphs, "index": index}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
