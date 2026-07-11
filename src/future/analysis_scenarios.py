"""Scenario-monitoring watchlist (Part C, closing slide) — NOT a forecast.
Three documented macro scenarios, each paired with which ALREADY-SCRAPED
series in this project would move first and in which direction. A
monitoring map for what to watch, not a prediction of what will happen.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, write_parquet

logger = logging.getLogger("clo_atlas.future.analysis_scenarios")

OUT_WATCHLIST = config.FINAL_DIR / "scenarios_watchlist.parquet"

# Each row: which already-built series to watch, and the DIRECTION this
# project would expect it to move first under that scenario — a hypothesis
# to monitor, not a fitted or backtested prediction.
WATCHLIST = [
    {"scenario": "Rate path down (cuts resume)", "series": "SOFR / floater coupon (src.macro)", "expected_direction": "down",
     "why": "CLO liability coupons are SOFR-floating; a falling base rate compresses income first, before any credit deterioration shows up"},
    {"scenario": "Rate path down (cuts resume)", "series": "CEF premium/discount (src.cef.analysis_capital_machine)", "expected_direction": "down",
     "why": "lower absolute yields typically compress the yield-chasing premium these vehicles have traded at"},
    {"scenario": "Credit cycle turn (defaults rise)", "series": "SLOOS net tightening (src.macro.analysis_tightening)", "expected_direction": "up",
     "why": "banks tighten lending standards before realized defaults rise, historically leading by several quarters"},
    {"scenario": "Credit cycle turn (defaults rise)", "series": "Regulatory alarm index (src.sentiment.analysis_alarm_v2)", "expected_direction": "up",
     "why": "regulator vulnerability language has historically spiked around realized stress episodes (COVID, the 2022 energy-crisis CLO tail-risk box)"},
    {"scenario": "Credit cycle turn (defaults rise)", "series": "AAA CLO mark dispersion (src.etf.analysis_tranche_panel)", "expected_direction": "up",
     "why": "cross-fund AAA mark disagreement widens when the underlying collateral's fair value becomes genuinely contested"},
    {"scenario": "Status quo (rates plateau, no cycle turn)", "series": "ATM issuance pace (src.cef.analysis_capital_machine)", "expected_direction": "flat-to-up",
     "why": "issuance has scaled up secularly regardless of premium size in the data so far; a status-quo scenario extends that trend"},
    {"scenario": "Status quo (rates plateau, no cycle turn)", "series": "Retail attention, Google Trends (src.future.scrape_trends)", "expected_direction": "flat-to-up",
     "why": "the registered product pipeline has kept growing every year measured; status quo implies continued retail-access institutionalization"},
]


def scenario_watchlist() -> pd.DataFrame:
    return pd.DataFrame(WATCHLIST)


def run() -> pd.DataFrame:
    df = scenario_watchlist()
    write_parquet(df, OUT_WATCHLIST, Provenance(
        parser="src.future.analysis_scenarios.scenario_watchlist", source_urls=[],
        notes="A monitoring map (which already-built series to watch and expected direction), not a forecast or fitted model.",
    ))
    logger.info("scenario_watchlist=%d rows across %d scenarios", len(df), df["scenario"].nunique())
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    print(run().to_string(index=False))


if __name__ == "__main__":
    main()
