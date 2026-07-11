"""Rebuilt regulatory alarm index (Section 6 v2) — additive, institution-
z-scored, components reported separately, coverage stated explicitly.

Supersedes analysis_alarm_index.py's multiplicative VADER-based index (kept
in place for the original Section 6 notebook; this module is what
notebooks/8_sentiment_v2.ipynb drives). Runs over whatever institutions are
present in data/interim/regulator_reports.parquet — currently Fed/BIS/ECB;
extending scrape_regulators_v2.py to add BoE/FSOC/OFR/congressional-testimony
sources means this module picks them up with no code change, since it
groups by whatever `institution` values actually appear.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet
from src.sentiment.scoring import additive_alarm_index, coverage_table, score_document

logger = logging.getLogger("clo_atlas.sentiment.analysis_alarm_v2")

REPORTS_PATH = config.INTERIM_DIR / "regulator_reports.parquet"

OUT_SECTIONS = config.FINAL_DIR / "alarm_v2_section_scores.parquet"
OUT_REPORT_LEVEL = config.FINAL_DIR / "alarm_v2_by_report.parquet"
OUT_COVERAGE = config.FINAL_DIR / "alarm_v2_coverage.parquet"


def section_scores() -> pd.DataFrame:
    if not REPORTS_PATH.exists():
        logger.warning("no regulator reports cached; run scrape_regulators.py first")
        return pd.DataFrame(columns=["institution", "date", "section", "vulnerability_rate", "lm_negative_rate"])
    reports = read_parquet(REPORTS_PATH)
    frames = [score_document(row["text"], row["institution"], row["date"]) for _, row in reports.iterrows()]
    frames = [f for f in frames if len(f)]
    if not frames:
        logger.warning("no CLO-mentioning sections found in any cached report")
        return pd.DataFrame(columns=["institution", "date", "section", "vulnerability_rate", "lm_negative_rate"])
    return pd.concat(frames, ignore_index=True)


def report_level_index(sections: pd.DataFrame) -> pd.DataFrame:
    if not REPORTS_PATH.exists():
        return pd.DataFrame(columns=["institution", "date", "mentions_per_1000", "alarm_index_v2"])
    reports = read_parquet(REPORTS_PATH)

    rows = []
    for _, report in reports.iterrows():
        from src.common.text import mention_rate_per_1000
        rate = mention_rate_per_1000(report["text"], ["CLO", "collateralized loan obligation"])
        mentions = rate["CLO"] + rate["collateralized loan obligation"]
        sub = sections[(sections["institution"] == report["institution"]) & (sections["date"] == report["date"])]
        rows.append({
            "institution": report["institution"], "date": report["date"], "mentions_per_1000": mentions,
            "n_sections": len(sub),
            "vulnerability_rate": sub["vulnerability_rate"].mean() if len(sub) else 0.0,
            "lm_negative_rate": sub["lm_negative_rate"].mean() if len(sub) and sub["lm_negative_rate"].notna().any() else 0.0,
            "lm_uncertainty_rate": sub["lm_uncertainty_rate"].mean() if len(sub) and sub["lm_uncertainty_rate"].notna().any() else 0.0,
        })
    report_level = pd.DataFrame(rows).sort_values("date")
    return additive_alarm_index(report_level)


def run() -> dict[str, pd.DataFrame]:
    sections = section_scores()
    write_parquet(sections, OUT_SECTIONS, Provenance(
        parser="src.sentiment.analysis_alarm_v2.section_scores", source_urls=[],
        notes="Domain scoring (LM negative/uncertainty + vulnerability lexicon), not VADER.",
    ))

    report_level = report_level_index(sections)
    write_parquet(report_level, OUT_REPORT_LEVEL, Provenance(
        parser="src.sentiment.analysis_alarm_v2.report_level_index", source_urls=[],
        notes="Additive index: z(mentions) + z(vulnerability_rate) + z(lm_negative_rate), z'd within institution.",
    ))

    reports = read_parquet(REPORTS_PATH) if REPORTS_PATH.exists() else pd.DataFrame()
    coverage = coverage_table(reports)
    write_parquet(coverage, OUT_COVERAGE, Provenance(parser="src.sentiment.analysis_alarm_v2.coverage_table", source_urls=[]))

    logger.info("sections=%d, report_level=%d reports across %d institutions, coverage=%d institution-years",
                len(sections), len(report_level), report_level["institution"].nunique() if len(report_level) else 0, len(coverage))
    return {"sections": sections, "report_level": report_level, "coverage": coverage}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
