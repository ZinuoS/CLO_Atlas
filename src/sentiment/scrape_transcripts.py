"""Earnings-call transcripts for CLO CEFs and public alt managers (Section
6) — STUBBED.

Same problem class as BDC N-CSR HTML tables (see src/edgar/scrape_bdc_soi.py's
docstring) but worse: there's no structured-XBRL equivalent for call
transcripts. Company IR sites each host replays/transcripts differently (some
as PDF exhibits to 8-Ks, some as third-party-hosted HTML, some audio-only),
so this would need one parser per company with no shared structure to
exploit — a materially larger effort than this project's remaining time
budget. Not gated/paywalled, just genuinely bespoke per filer.

`run()` is the documented entry point analysis_insider_tone.py expects, kept
stubbed rather than partially implemented for 1-2 companies in a way that
would look more complete than it is.
"""
from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger("clo_atlas.sentiment.scrape_transcripts")


def run() -> pd.DataFrame:
    logger.warning(
        "scrape_transcripts.py is stubbed — no shared structure across issuer IR sites to exploit "
        "(unlike BDC SOI's XBRL fragments); would need one parser per company. See module docstring."
    )
    return pd.DataFrame(columns=["company", "date", "quarter", "speaker_role", "text"])


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
