"""Nonbank share of corporate lending, and the loans-vs-bonds mix in
corporate debt outstanding (slide 2: "Banks stepped back. A trillion-dollar
market stepped in.").

Both computed from src.macro.scrape_z1's FRED-mirrored Z.1 series, back to
1945:Q4. Structural landmarks (Basel III finalization, 2013 leveraged-lending
guidance, COVID) are annotated at viz time from config.EVENTS-style dates
defined here, not fitted to the data.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.macro.analysis_disintermediation")

Z1_PATH = config.INTERIM_DIR / "macro_z1_series.parquet"

OUT_NONBANK_SHARE = config.FINAL_DIR / "macro_nonbank_lending_share.parquet"
OUT_LOANS_VS_BONDS = config.FINAL_DIR / "macro_loans_vs_bonds_mix.parquet"

# Point-in-time structural landmarks for the disintermediation chart, each a
# citable regulatory/market event rather than a data-derived breakpoint.
STRUCTURAL_LANDMARKS = [
    {"date": "2013-03-01", "label": "2013 leveraged-lending guidance"},
    {"date": "2017-12-01", "label": "Basel III finalized ('Basel IV')"},
    {"date": "2020-03-01", "label": "COVID-19 shock"},
]


def _load_z1_wide() -> pd.DataFrame:
    if not Z1_PATH.exists():
        return pd.DataFrame()
    z1 = read_parquet(Z1_PATH)
    z1["date"] = pd.to_datetime(z1["date"])
    wide = z1.pivot_table(index="date", columns="series", values="value").sort_index()
    return wide


def nonbank_lending_share() -> pd.DataFrame:
    """Nonbank share of nonfinancial-corporate-business loans (all lenders):
    1 - (depository-institution loans / total loans), where total loans =
    total credit market debt - debt securities."""
    wide = _load_z1_wide()
    required = ["nonfin_corp_total_credit_market_debt", "nonfin_corp_debt_securities", "nonfin_corp_bank_loans"]
    if wide.empty or not all(c in wide.columns for c in required):
        logger.warning("Z.1 series incomplete; nonbank_lending_share is empty")
        return pd.DataFrame(columns=["date", "total_loans", "bank_loans", "nonbank_share"])

    total_loans = wide["nonfin_corp_total_credit_market_debt"] - wide["nonfin_corp_debt_securities"]
    bank_loans = wide["nonfin_corp_bank_loans"]
    nonbank_share = 1 - (bank_loans / total_loans)

    out = pd.DataFrame({
        "date": wide.index, "total_loans": total_loans.values,
        "bank_loans": bank_loans.values, "nonbank_share": nonbank_share.values,
    }).dropna(subset=["nonbank_share"])
    out["decade"] = (out["date"].dt.year // 10) * 10
    return out


def loans_vs_bonds_mix() -> pd.DataFrame:
    """Loans vs. bonds share of nonfinancial corporate debt outstanding."""
    wide = _load_z1_wide()
    required = ["nonfin_corp_total_credit_market_debt", "nonfin_corp_debt_securities"]
    if wide.empty or not all(c in wide.columns for c in required):
        logger.warning("Z.1 series incomplete; loans_vs_bonds_mix is empty")
        return pd.DataFrame(columns=["date", "loans", "bonds", "loans_share", "bonds_share"])

    total = wide["nonfin_corp_total_credit_market_debt"]
    bonds = wide["nonfin_corp_debt_securities"]
    loans = total - bonds
    out = pd.DataFrame({
        "date": wide.index, "loans": loans.values, "bonds": bonds.values,
        "loans_share": (loans / total).values, "bonds_share": (bonds / total).values,
    })
    return out


def decade_change_summary(nonbank: pd.DataFrame) -> pd.DataFrame:
    """Decade-on-decade change in the nonbank lending share — the number that
    carries the "structural, not cyclical" argument."""
    if nonbank.empty:
        return pd.DataFrame(columns=["decade", "avg_nonbank_share", "change_from_prior_decade"])
    by_decade = nonbank.groupby("decade")["nonbank_share"].mean().reset_index(name="avg_nonbank_share")
    by_decade["change_from_prior_decade"] = by_decade["avg_nonbank_share"].diff()
    return by_decade


def run() -> dict[str, pd.DataFrame]:
    nonbank = nonbank_lending_share()
    write_parquet(nonbank, OUT_NONBANK_SHARE, Provenance(
        parser="src.macro.analysis_disintermediation.nonbank_lending_share", source_urls=[]))

    mix = loans_vs_bonds_mix()
    write_parquet(mix, OUT_LOANS_VS_BONDS, Provenance(
        parser="src.macro.analysis_disintermediation.loans_vs_bonds_mix", source_urls=[]))

    decade_summary = decade_change_summary(nonbank)
    logger.info("nonbank_share=%d quarters, loans_vs_bonds=%d quarters, decades=%d",
                len(nonbank), len(mix), len(decade_summary))
    if len(decade_summary):
        logger.info("decade summary:\n%s", decade_summary.to_string(index=False))
    return {"nonbank_share": nonbank, "loans_vs_bonds": mix, "decade_summary": decade_summary}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
