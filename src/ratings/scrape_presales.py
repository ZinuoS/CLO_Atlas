"""S&P/Fitch CLO presale report PDFs (Section 5) — STUBBED.

Same access wall as scrape_actions.py (see that module's docstring and
docs/excluded_sources.md): S&P is Akamai-blocked outright, Fitch's presale
listings are client-rendered with no free API. Presale PDFs themselves sit
one click further behind those same gates, so there is no shortcut here.

`run()` is the documented entry point analysis_vocabulary.py and
analysis_structure_drift.py expect, kept stubbed rather than worked around.
"""
from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger("clo_atlas.ratings.scrape_presales")


def run() -> pd.DataFrame:
    logger.warning(
        "scrape_presales.py is stubbed — same S&P/Fitch access wall as scrape_actions.py. "
        "See docs/excluded_sources.md."
    )
    return pd.DataFrame(columns=["date", "agency", "deal", "raw_text", "pdf_path"])


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
