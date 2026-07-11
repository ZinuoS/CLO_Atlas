"""Distribution-cut resilience (Section 2 deep-dive): does OXLC's premium
survive a distribution cut? — the retail-stickiness question.

Distribution history and cut/raise event detection already exist from
Section 2 (`cef_distribution_history.parquet`, `cef_distribution_change_
events.parquet`); this module doesn't redo that work. It adds the one
genuinely new angle the deep-dive needs: joining those already-detected cut
events against this section's own real historical premium/discount series
(`analysis_capital_machine.premium_history`, built from OXLC's disclosed
NAV estimates — Section 2's own premium/discount table is limited to a
single current-day snapshot and can't answer this question at all).
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.cef.analysis_capital_machine import premium_history
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.cef.analysis_distribution_quality")

CHANGE_EVENTS_PATH = config.FINAL_DIR / "cef_distribution_change_events.parquet"

OUT_CUTS_VS_PREMIUM = config.FINAL_DIR / "distribution_cuts_vs_premium.parquet"


def cuts_vs_premium(fund: str = "OXLC") -> pd.DataFrame:
    if not CHANGE_EVENTS_PATH.exists():
        logger.warning("no distribution-change-events data cached; cuts_vs_premium is empty")
        return pd.DataFrame(columns=["ex_date", "change_pct", "premium_before", "premium_after"])
    events = read_parquet(CHANGE_EVENTS_PATH)
    events = events[events["ticker"] == fund].copy()
    events["ex_date"] = pd.to_datetime(events["ex_date"]).dt.tz_localize(None)
    cuts = events[events["change_pct"] < 0].sort_values("ex_date")
    if cuts.empty:
        return pd.DataFrame(columns=["ex_date", "change_pct", "premium_before", "premium_after"])

    premium = premium_history(fund=fund)
    if premium.empty:
        logger.warning("no premium history for %s; cuts_vs_premium reports cuts without premium context", fund)
        return cuts[["ex_date", "change_pct"]]

    rows = []
    for _, cut in cuts.iterrows():
        before = premium[premium["date"] <= cut["ex_date"]].tail(1)
        after = premium[premium["date"] > cut["ex_date"]].head(1)
        rows.append({
            "ex_date": cut["ex_date"], "change_pct": cut["change_pct"],
            "premium_before": before["premium_discount"].iloc[0] if len(before) else None,
            "premium_after": after["premium_discount"].iloc[0] if len(after) else None,
        })
    return pd.DataFrame(rows)


def run() -> pd.DataFrame:
    out = cuts_vs_premium()
    write_parquet(out, OUT_CUTS_VS_PREMIUM, Provenance(
        parser="src.cef.analysis_distribution_quality.cuts_vs_premium", source_urls=[],
        notes="Distribution cuts from Section 2's cef_distribution_change_events.parquet; premium context from "
              "this section's own disclosed-NAV-based premium_history (not Section 2's single-snapshot table).",
    ))
    logger.info("cuts_vs_premium=%d cut events with premium context", len(out))
    return out


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
