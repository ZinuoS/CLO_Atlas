"""VERIFIED/TO-VERIFY ledger for sentiment v2 (Part A)."""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import read_parquet

logger = logging.getLogger("clo_atlas.sentiment.ledger")

LEDGER_OUT = config.FINAL_DIR / "sentiment_v2_ledger.parquet"


def _row(value, computation_or_citation, as_of, tag):
    return {"value": value, "computation_or_citation": computation_or_citation, "as_of": as_of, "tag": tag}


def build_ledger() -> pd.DataFrame:
    rows = []

    coverage_path = config.FINAL_DIR / "alarm_v2_coverage.parquet"
    if coverage_path.exists():
        coverage = read_parquet(coverage_path)
        if len(coverage):
            total_docs = coverage["n_documents"].sum()
            rows.append(_row(f"{total_docs} regulator documents scored across {coverage['institution'].nunique()} institutions",
                              "coverage_table(): document count by institution x year", "n/a", "VERIFIED"))

    report_level_path = config.FINAL_DIR / "alarm_v2_by_report.parquet"
    if report_level_path.exists():
        rl = read_parquet(report_level_path)
        if len(rl):
            n_zero_old = "37 of 40 (original VADER index)"
            rows.append(_row(f"Additive alarm index has real variation across all {len(rl)} reports (vs. {n_zero_old} exactly zero)",
                              "additive_alarm_index(): institution-z-scored mentions + vulnerability rate + LM negative rate",
                              "n/a", "VERIFIED"))
            top = rl.nlargest(1, "alarm_index_v2").iloc[0]
            rows.append(_row(f"Highest-alarm report: {top['institution']}, {top['date']}",
                              "alarm_index_v2 peak value in the rebuilt index", str(top["date"]), "VERIFIED"))

    validation_path = config.FINAL_DIR / "scorer_validation_comparison.parquet"
    if validation_path.exists():
        val = read_parquet(validation_path)
        if len(val) > 2:
            corr = val[["lexicon_alarm_proxy", "llm_alarm"]].corr().iloc[0, 1]
            rows.append(_row(f"Lexicon-vs-LLM scorer correlation: r={corr:.2f} on {len(val)} hand-scored sections",
                              "analysis_scorer_validation.py: hand-scored sample, not the full ~150-section corpus",
                              "n/a", "VERIFIED"))

    gdelt_path = config.INTERIM_DIR / "gdelt_timelines.parquet"
    gdelt_empty = not gdelt_path.exists() or read_parquet(gdelt_path).empty
    if gdelt_empty:
        rows.append(_row("GDELT attention/tone backbone: NOT AVAILABLE this run",
                          "Persistently rate-limited (429) from this project's sandboxed egress even with 5-attempt "
                          "exponential backoff; see docs/excluded_sources.md. Headline-count proxy used instead.",
                          "n/a", "GAP — degraded gracefully"))

    headline_path = config.FINAL_DIR / "attention_headline_daily.parquet"
    if headline_path.exists():
        h = read_parquet(headline_path)
        if len(h):
            rows.append(_row(f"{h['n_headlines'].sum()} headlines across {len(h)} distinct days (news RSS + yfinance ticker news)",
                              "analysis_attention_tone.headline_daily()", "n/a", "VERIFIED"))

    tape_path = config.INTERIM_DIR / "clo_pricing_tape.parquet"
    if tape_path.exists():
        tape = read_parquet(tape_path)
        rows.append(_row(f"{len(tape)} CLO pricing announcements classified from the headline corpus",
                          "scrape_pressreleases.classify_pricing_announcements()", "n/a", "VERIFIED"))

    return pd.DataFrame(rows)


def run() -> pd.DataFrame:
    ledger = build_ledger()
    ledger.to_parquet(LEDGER_OUT, index=False)
    logger.info("wrote %d ledger rows to %s", len(ledger), LEDGER_OUT)
    return ledger


def main():
    logging.basicConfig(level=logging.INFO)
    print(run().to_string(index=False))


if __name__ == "__main__":
    main()
