"""VERIFIED/TO-VERIFY ledger for the CEF/Oxford Lane deep-dive (Part B)."""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import read_parquet

logger = logging.getLogger("clo_atlas.cef.ledger")

LEDGER_OUT = config.FINAL_DIR / "cef_deep_dive_ledger.parquet"


def _row(value, computation_or_citation, as_of, tag):
    return {"value": value, "computation_or_citation": computation_or_citation, "as_of": as_of, "tag": tag}


def build_ledger() -> pd.DataFrame:
    rows = []

    issuance_path = config.FINAL_DIR / "capital_machine_incremental_issuance.parquet"
    if issuance_path.exists():
        issuance = read_parquet(issuance_path)
        if len(issuance):
            total = issuance["incremental_net_proceeds_millions"].sum()
            rows.append(_row(f"${total:,.0f}M raised via OXLC's ATM program since 2016",
                              "analysis_capital_machine.incremental_issuance(), from OXLC's own EDGAR 424B3/497 filings",
                              str(issuance["filing_date"].max()), "VERIFIED"))

    premium_path = config.FINAL_DIR / "capital_machine_premium_history.parquet"
    if premium_path.exists():
        premium = read_parquet(premium_path).sort_values("date")
        if len(premium):
            trailing_negative = 0
            for v in premium["premium_discount"].iloc[::-1]:
                if v < 0:
                    trailing_negative += 1
                else:
                    break
            rows.append(_row(f"Disclosed premium/discount ranges {premium['premium_discount'].min()*100:.0f}% to "
                              f"{premium['premium_discount'].max()*100:.0f}%; every observation since "
                              f"{premium['date'].iloc[-trailing_negative].strftime('%b %Y') if trailing_negative else 'n/a'} "
                              f"has been a discount ({trailing_negative} consecutive readings)",
                              "analysis_capital_machine.premium_history(), merging OXLC's 424B3 ATM supplements and its own "
                              "NAV-update press releases, rescaled for OXLC's 2025-09-08 1-for-5 reverse split",
                              str(premium["date"].max()), "VERIFIED"))
            rows.append(_row("Bug caught and fixed: unrescaled comparison against pre-split NAV produced a nonsense 813% 'premium'",
                              "see analysis_capital_machine.py docstring and test_analysis_capital_machine.py's regression test",
                              "n/a", "VERIFIED"))
            rows.append(_row("Second bug caught and fixed: a press release published after the split restates its own prior-"
                              "period comparison NAV on the current share basis already; rescaling by as-of date (correct for "
                              "the 424B3 channel) double-counted the split for press-release rows, inflating one point 5x "
                              "($20.60 -> $103.00). Fixed by keying the rescale off each figure's publication date instead.",
                              "see analysis_capital_machine.py docstring and test_analysis_capital_machine.py's regression test",
                              "n/a", "VERIFIED"))

    margin_path = config.FINAL_DIR / "cost_of_capital_margin.parquet"
    if margin_path.exists():
        margin = read_parquet(margin_path)
        for _, r in margin.iterrows():
            rows.append(_row(f"{r['fund']}: portfolio yield {r['portfolio_effective_yield']:.1f}% vs. "
                              f"blended preferred cost {r['blended_cost_of_capital']*100:.1f}% (+{r['margin']*100:.1f}pp margin)",
                              "analysis_cost_of_capital.cost_of_capital_margin()", "n/a", "VERIFIED"))

    beta_path = config.FINAL_DIR / "nav_translation_beta.parquet"
    if beta_path.exists():
        beta = read_parquet(beta_path)
        for _, r in beta.iterrows():
            rows.append(_row(f"{r['ticker']}: price beta to BKLN = {r['beta_to_bkln']:.2f}",
                              "analysis_nav_translation.price_beta_to_loans() — price proxy, not true NAV beta",
                              "n/a", "VERIFIED"))

    ownership_path = config.FINAL_DIR / "ownership_institutional_floor.parquet"
    if ownership_path.exists():
        own = read_parquet(ownership_path)
        for _, r in own.iterrows():
            rows.append(_row(f"{r['ticker']}: >=5%-holder institutional floor {r['institutional_floor_pct']:.1f}%",
                              "analysis_ownership.institutional_floor(), from EDGAR Schedule 13G/13G-A — a lower bound, not complete institutional share",
                              "n/a", "VERIFIED"))

    chain_path = config.FINAL_DIR / "demand_transmission_chain_status.parquet"
    if chain_path.exists():
        chain = read_parquet(chain_path)
        for _, r in chain.iterrows():
            tag = "GAP — not plotted" if r["status"] == "GAP" else "VERIFIED"
            rows.append(_row(f"{r['link']}: {r['status']}", r["detail"], "n/a", tag))

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
