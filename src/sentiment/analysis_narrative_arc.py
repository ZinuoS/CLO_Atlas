"""The "new CDOs" narrative arc (Section 6): frequency of CDO/2008-comparison
language in the regulator report corpus over time.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet
from src.common.text import mention_rate_per_1000

logger = logging.getLogger("clo_atlas.sentiment.analysis_narrative_arc")

REPORTS_PATH = config.INTERIM_DIR / "regulator_reports.parquet"
OUT_PATH = config.FINAL_DIR / "cdo_comparison_frequency.parquet"

CDO_TERMS = ["like CDOs", "reminiscent of 2008", "subprime", "similar to the mortgage crisis",
             "collateralized debt obligation", "financial crisis of 2008"]


def cdo_comparison_frequency() -> pd.DataFrame:
    if not REPORTS_PATH.exists():
        logger.warning("no regulator reports cached; run scrape_regulators.py first")
        return pd.DataFrame(columns=["institution", "date", "term", "mentions_per_1000"])
    reports = read_parquet(REPORTS_PATH)
    rows = []
    for _, report in reports.iterrows():
        rates = mention_rate_per_1000(report["text"], CDO_TERMS)
        for term, rate in rates.items():
            rows.append({"institution": report["institution"], "date": report["date"],
                        "term": term, "mentions_per_1000": rate})
    return pd.DataFrame(rows)


def run() -> pd.DataFrame:
    df = cdo_comparison_frequency()
    write_parquet(df, OUT_PATH, Provenance(parser="src.sentiment.analysis_narrative_arc.cdo_comparison_frequency", source_urls=[]))
    logger.info("cdo_comparison_frequency=%d rows", len(df))
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
