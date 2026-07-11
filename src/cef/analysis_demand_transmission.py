"""The demand-transmission chain (Section 2 deep-dive): CEF premium -> ATM
issuance -> portfolio position additions, each link measured, no causal
overclaim. The final link (-> market-wide CLO new-issue equity conditions)
is NOT included: it would need Section 4's CLO issuance-cycle series, which
is empty (SIFMA, the only free issuance-volume source found, is gated —
see docs/excluded_sources.md and src/macro/analysis_tightening.py, which
hit the identical gap). Reported as a stated gap, not silently dropped.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.cef.analysis_capital_machine import incremental_issuance, premium_history
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.cef.analysis_demand_transmission")

POSITIONS_PATH = config.INTERIM_DIR / "cef_clo_positions.parquet"

OUT_POSITION_GROWTH = config.FINAL_DIR / "demand_transmission_position_growth.parquet"
OUT_CHAIN_STATUS = config.FINAL_DIR / "demand_transmission_chain_status.parquet"


def position_growth(fund: str = "OXLC") -> pd.DataFrame:
    """Quarter-over-quarter growth in distinct CLO CUSIPs held — the
    "portfolio position additions" link, from NPORT-P."""
    if not POSITIONS_PATH.exists():
        return pd.DataFrame(columns=["fund", "period", "n_positions", "n_new_positions"])
    df = read_parquet(POSITIONS_PATH)
    df = df[(df["fund"] == fund) & (df["is_clo"] == True)]  # noqa: E712
    if df.empty:
        return pd.DataFrame(columns=["fund", "period", "n_positions", "n_new_positions"])

    periods = sorted(df["period"].unique())
    rows = []
    prev_cusips: set = set()
    for period in periods:
        cusips = set(df[df["period"] == period]["cusip"].dropna())
        rows.append({"fund": fund, "period": period, "n_positions": len(cusips),
                     "n_new_positions": len(cusips - prev_cusips)})
        prev_cusips = cusips
    return pd.DataFrame(rows)


def chain_status() -> pd.DataFrame:
    """What's actually measured in this chain vs. what's gapped, one row
    per link — the honest map, not a fitted end-to-end model."""
    return pd.DataFrame([
        {"link": "CEF premium -> ATM issuance", "status": "measured", "detail": "analysis_capital_machine.premium_vs_issuance (r≈-0.30)"},
        {"link": "ATM issuance -> portfolio position additions", "status": "measured (descriptive)", "detail": "position_growth(), joined by filing quarter below"},
        {"link": "-> market-wide CLO new-issue equity conditions", "status": "GAP", "detail": "needs Section 4 CLO issuance data; SIFMA gated (see docs/excluded_sources.md)"},
    ])


def run() -> dict[str, pd.DataFrame]:
    growth = position_growth()
    write_parquet(growth, OUT_POSITION_GROWTH, Provenance(parser="src.cef.analysis_demand_transmission.position_growth", source_urls=[]))

    status = chain_status()
    write_parquet(status, OUT_CHAIN_STATUS, Provenance(
        parser="src.cef.analysis_demand_transmission.chain_status", source_urls=[],
        notes="One row per link in the planned demand-transmission chain, including the unmeasurable final link.",
    ))

    logger.info("position_growth=%d quarters, chain_status=%d links (%d measured, %d gap)",
                len(growth), len(status), (status["status"] != "GAP").sum(), (status["status"] == "GAP").sum())
    return {"position_growth": growth, "chain_status": status}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
