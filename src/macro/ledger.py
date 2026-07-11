"""VERIFIED/TO-VERIFY ledger for the macro opener (slides 1-2).

Every number that could reach a slide gets one row here, built entirely from
this section's own final-stage parquet outputs (never hardcoded), tagged
VERIFIED (computed in this repo) or TO-VERIFY (an external figure quoted from
a source). Run after every analysis_*.run() has produced its output.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import read_parquet
from src.macro.analysis_scale import SCALE_CITATIONS

logger = logging.getLogger("clo_atlas.macro.ledger")

LEDGER_OUT = config.FINAL_DIR / "macro_ledger.parquet"


def _row(value: str, computation_or_citation: str, as_of: str, tag: str) -> dict:
    return {"value": value, "computation_or_citation": computation_or_citation, "as_of": as_of, "tag": tag}


def build_ledger() -> pd.DataFrame:
    rows: list[dict] = []

    # --- Slide 1: regime ---------------------------------------------------
    regime_path = config.FINAL_DIR / "macro_rate_regime.parquet"
    if regime_path.exists():
        regime = read_parquet(regime_path)
        if len(regime):
            latest = regime.iloc[-1]
            rows.append(_row(f"{latest['regime']} at {latest['fedfunds']:.2f}%",
                              "rate_regime_labels(): rule-based label on FEDFUNDS "
                              f"(ZIRP <= {config.MACRO_ZIRP_THRESHOLD_PCT}%, hike/ease on a {config.MACRO_REGIME_ROC_THRESHOLD_PCT}pt 12m change)",
                              str(pd.Timestamp(latest["date"]).date()), "VERIFIED"))

    dd_path = config.FINAL_DIR / "macro_duration_pain_drawdown.parquet"
    if dd_path.exists():
        dd = read_parquet(dd_path)
        for _, r in dd.iterrows():
            rows.append(_row(f"{r['ticker']}: {r['max_drawdown']*100:+.0f}% trough, "
                              f"{'recovered' if r['recovered'] else 'not recovered'}",
                              "duration_pain_drawdown(): max drawdown from Dec 2021 to latest cached price",
                              str(pd.Timestamp(r["as_of"]).date()), "VERIFIED"))

    # --- Slide 2: disintermediation -----------------------------------------
    nonbank_path = config.FINAL_DIR / "macro_nonbank_lending_share.parquet"
    if nonbank_path.exists():
        nonbank = read_parquet(nonbank_path)
        if len(nonbank):
            latest = nonbank.iloc[-1]
            q = (pd.Timestamp(latest["date"]).month - 1) // 3 + 1
            rows.append(_row(f"{latest['nonbank_share']:.0%} nonbank share of corporate lending",
                              "nonbank_lending_share(): 1 - (bank loans / total loans), from FRED Z.1 (BOGZ1) series",
                              f"{pd.Timestamp(latest['date']).year} Q{q}", "VERIFIED"))

    # --- Slide 2: scale ------------------------------------------------------
    comparison_path = config.FINAL_DIR / "macro_market_size_comparison.parquet"
    if comparison_path.exists():
        comparison = read_parquet(comparison_path)
        for _, r in comparison.iterrows():
            tag = "TO-VERIFY" if r["to_verify"] else "VERIFIED"
            rows.append(_row(f"{r['market']}: ${r['value_usd_millions']/1e6:.2f}T outstanding",
                              "market_size_comparison(): FRED-mirrored Fed/Treasury series" if not r["to_verify"]
                              else f"Section 4 citation: {config.FED_CLO_HOLDER_CITATION['source_title']}",
                              str(r["as_of"]), tag))

    for citation in SCALE_CITATIONS:
        rows.append(_row(citation["claim"], citation["source"], citation["as_of"], "TO-VERIFY"))

    issuance_path = config.FINAL_DIR / "clo_issuance_cycle.parquet"
    issuance_empty = not issuance_path.exists() or read_parquet(issuance_path).empty
    if issuance_empty:
        rows.append(_row("CLO issuance volume: NOT AVAILABLE",
                          "SIFMA (only free issuance-volume source found) is gated; see docs/excluded_sources.md",
                          "n/a", "GAP — not plotted"))

    # --- Slide 2 support: tightening ------------------------------------------
    sloos_path = config.FINAL_DIR / "macro_sloos_history.parquet"
    if sloos_path.exists():
        sloos = read_parquet(sloos_path)
        if len(sloos):
            latest = sloos.iloc[-1]
            rows.append(_row(f"SLOOS net tightening: {latest['net_pct_tightening']:.0f} ({latest['percentile']:.0%}ile of history)",
                              "sloos_history(): FRED (DRTSCILM), percentile rank within its own full history",
                              str(pd.Timestamp(latest["date"]).date()), "VERIFIED"))

    xcorr_path = config.FINAL_DIR / "macro_sloos_vs_lending_xcorr.parquet"
    if xcorr_path.exists():
        xcorr = read_parquet(xcorr_path)
        if len(xcorr):
            best = xcorr.iloc[-1]
            rows.append(_row(f"SLOOS-vs-C&I-loan-growth correlation at {int(best['lead_quarters'])}Q lead: {best['correlation']:.2f}",
                              "sloos_vs_lending_xcorr(): descriptive cross-correlation, FRED (DRTSCILM, BUSLOANS) — not a causal estimate",
                              "n/a", "VERIFIED"))

    # --- Appendix: income ----------------------------------------------------
    spread_path = config.FINAL_DIR / "macro_spread_comparison.parquet"
    if spread_path.exists():
        spreads = read_parquet(spread_path)
        for _, r in spreads.iterrows():
            rows.append(_row(f"{r['market']} OAS: {r['oas_pct']:.2f}pp",
                              "spread_comparison(): FRED (ICE BofA OAS series)",
                              str(pd.Timestamp(r["as_of"]).date()), "VERIFIED"))

    carry_path = config.FINAL_DIR / "macro_carry_per_duration.parquet"
    if carry_path.exists():
        carry = read_parquet(carry_path)
        for _, r in carry.iterrows():
            rows.append(_row(f"{r['ticker']}: yield {r['yield_pct']*100:.1f}% ({r['yield_label']}), "
                              f"duration {r['effective_duration_years']:.2f}yr",
                              "scrape_fund_characteristics(): scraped from the fund's own overview page",
                              str(pd.Timestamp.today().date()), "VERIFIED"))

    return pd.DataFrame(rows)


def run() -> pd.DataFrame:
    ledger = build_ledger()
    ledger.to_parquet(LEDGER_OUT, index=False)
    logger.info("wrote %d ledger rows to %s (%d VERIFIED, %d TO-VERIFY, %d gaps)",
                len(ledger), LEDGER_OUT, (ledger["tag"] == "VERIFIED").sum(),
                (ledger["tag"] == "TO-VERIFY").sum(), (ledger["tag"] == "GAP — not plotted").sum())
    return ledger


def main():
    logging.basicConfig(level=logging.INFO)
    print(run().to_string(index=False))


if __name__ == "__main__":
    main()
