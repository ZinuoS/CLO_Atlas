"""Warehouse-facility economics: the pre-closing period where the manager
ramps a loan portfolio using warehouse debt + at-risk equity capital,
before the CLO prices and takes out the warehouse at closing.

Two different things are mixed together here, and this module keeps them
labeled separately rather than blending them into one undifferentiated
TO-VERIFY chart:

  1. TIMING is real and VERIFIED. The refinancing circular's "General"
     section on the Issuer states the entity was incorporated January 20,
     2023 as "Courchevel Warehouse Ltd." (Jersey, registered no. 147155)
     and was renamed to "HPS Loan Management 2023-17, Ltd." on March 14,
     2023; the circular separately defines March 29, 2023 as the "Original
     Closing Date." That's a real ~68-day pre-closing window, not an
     assumed one (config.ANATOMY_ORIGINAL_HISTORY).
  2. ECONOMICS are not disclosable and stay TO-VERIFY. Warehouse lending
     terms (advance rate, financing spread) are a private bilateral
     arrangement between the arranger/warehouse lender and the manager,
     never disclosed in any CLO's public offering circular -- this is a
     structural fact about the CLO market, not a gap specific to this
     deal or this project's research (confirmed: the circular states "The
     Issuer does not publish any financial statements," and ongoing
     investor reporting runs through a restricted third-party platform,
     not a public one -- config.ANATOMY_ORIGINAL_HISTORY's reporting_note).
     Every dollar figure below is a market-standard convention
     (config.ANATOMY_WAREHOUSE), derived arithmetic on top of that
     convention, not a circular figure.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config
from src.anatomy.deal import Deal, load_deal
from src.common.cache import Provenance, write_parquet


def _s_curve_ramp(n_points: int) -> np.ndarray:
    """Cumulative fraction of target par ramped by each grid point — slow
    start (sourcing loans takes time), fast middle, slow finish (chasing
    the last few names before closing) — the standard shape a warehouse
    ramp takes, not a naive linear accumulation."""
    x = np.linspace(-3, 3, n_points)
    logistic = 1 / (1 + np.exp(-x))
    return (logistic - logistic[0]) / (logistic[-1] - logistic[0])


def build_warehouse_schedule(deal: Deal | None = None) -> pd.DataFrame:
    deal = deal or load_deal()
    w = config.ANATOMY_WAREHOUSE
    hist = config.ANATOMY_ORIGINAL_HISTORY

    # Real dates (VERIFIED, see module docstring), weekly grid -- the actual
    # window is ~68 days / ~9.7 weeks, short enough that quarterly points
    # (the old convention, and still what the rest of this section uses for
    # the post-closing liability engine) would be too coarse to show a shape.
    ramp_start = pd.Timestamp(hist["incorporation_date"])
    original_closing = pd.Timestamp(hist["original_closing_date"])
    weeks = pd.date_range(ramp_start, original_closing, freq="W")
    if weeks.empty or weeks[-1] != original_closing:
        weeks = weeks.append(pd.DatetimeIndex([original_closing]))
    if weeks[0] != ramp_start:
        weeks = pd.DatetimeIndex([ramp_start]).append(weeks)

    cum_frac = _s_curve_ramp(len(weeks))
    target_par = w["target_ramp_par"]
    cum_par = cum_frac * target_par
    advance_rate = w["advance_rate_pct"] / 100
    days_elapsed = (weeks - ramp_start).days.to_numpy()

    rows = []
    for i, (date, days) in enumerate(zip(weeks, days_elapsed)):
        par = cum_par[i]
        debt_drawn = par * advance_rate
        equity_at_risk = par - debt_drawn
        # Carry on the ramped balance since the prior grid point: loans earn
        # SOFR+WAS, warehouse debt costs SOFR+warehouse spread -- the SOFR
        # legs cancel, leaving a spread-only carry (the standard
        # warehouse-arb framing), accrued over the actual day-count between
        # grid points rather than an assumed quarterly chunk.
        prior_par = cum_par[i - 1] if i > 0 else 0.0
        prior_days = days_elapsed[i - 1] if i > 0 else 0
        day_frac_of_year = max(days - prior_days, 0) / 365.0
        loan_income = prior_par * (w["loan_yield_bps_over_sofr"] / 100) / 100 * day_frac_of_year
        debt_cost = (prior_par * advance_rate) * (w["spread_bps_over_sofr"] / 100) / 100 * day_frac_of_year
        net_carry_to_equity = loan_income - debt_cost
        rows.append(dict(
            date=date, days_since_incorporation=days, cumulative_par=par,
            warehouse_debt_drawn=debt_drawn, equity_at_risk=equity_at_risk,
            net_carry_to_equity=net_carry_to_equity,
        ))
    df = pd.DataFrame(rows)
    df["cumulative_net_carry"] = df["net_carry_to_equity"].cumsum()

    max_equity_at_risk = df["equity_at_risk"].max()
    clo_equity_size = deal.tranche("equity").size
    # ISO strings, not Timestamps: pandas' to_parquet JSON-serializes df.attrs
    # as file metadata, and a raw Timestamp isn't JSON-serializable.
    df.attrs["ramp_start_date"] = ramp_start.isoformat()
    df.attrs["original_closing_date"] = original_closing.isoformat()
    df.attrs["ramp_days"] = int((original_closing - ramp_start).days)
    df.attrs["max_equity_at_risk"] = max_equity_at_risk
    df.attrs["clo_equity_size"] = clo_equity_size
    df.attrs["equity_at_risk_pct_of_clo_equity"] = 100 * max_equity_at_risk / clo_equity_size
    df.attrs["total_ramp_carry_to_equity"] = df["net_carry_to_equity"].sum()
    return df


def main():
    df = run()
    print(df.to_string(index=False))
    print(f"\nReal ramp window: {df.attrs['ramp_start_date'].date()} to {df.attrs['original_closing_date'].date()} "
          f"({df.attrs['ramp_days']} days) -- VERIFIED, from the circular's Issuer history")
    print(f"Peak warehouse equity at risk: ${df.attrs['max_equity_at_risk']:,.0f} "
          f"({df.attrs['equity_at_risk_pct_of_clo_equity']:.1f}% of the eventual CLO equity tranche size) -- TO-VERIFY economics")
    print(f"Total carry earned by warehouse equity during ramp: ${df.attrs['total_ramp_carry_to_equity']:,.0f} -- TO-VERIFY economics")


def run(deal: Deal | None = None) -> pd.DataFrame:
    deal = deal or load_deal()
    df = build_warehouse_schedule(deal)
    out_path = config.FINAL_DIR / "anatomy" / "warehouse_schedule.parquet"
    write_parquet(df, out_path, Provenance(
        source_urls=[deal.citation.get("source_url", "")],
        parser="src.anatomy.analysis_warehouse.build_warehouse_schedule",
        notes="Ramp TIMING (dates) is VERIFIED, from the circular's Issuer-history section (incorporation as "
              "'Courchevel Warehouse Ltd.', renamed, Original Closing Date). Ramp ECONOMICS (advance rate, "
              "financing spread, and everything derived from them) are TO-VERIFY market-standard conventions "
              "(config.ANATOMY_WAREHOUSE) -- warehouse lending terms are never disclosed in a public offering "
              "circular, structurally, for any CLO.",
    ))
    return df


if __name__ == "__main__":
    main()
