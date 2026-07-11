"""Warehouse-facility economics: the pre-closing period where the manager
ramps a loan portfolio using warehouse debt + at-risk equity capital,
before the CLO prices and takes out the warehouse at closing.

Warehouse lending terms are a private arrangement never disclosed in a
public offering circular — every parameter here is a market-standard
convention (config.ANATOMY_WAREHOUSE), not a circular figure. This module
is honest about that: every output column is derived from TO-VERIFY inputs.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config
from src.anatomy.deal import Deal, load_deal
from src.common.cache import Provenance, write_parquet


def _s_curve_ramp(n_quarters: int) -> np.ndarray:
    """Cumulative fraction of target par ramped by each quarter — slow
    start (sourcing loans takes time), fast middle, slow finish (chasing
    the last few names before closing) — the standard shape a warehouse
    ramp takes, not a naive linear accumulation."""
    x = np.linspace(-3, 3, n_quarters + 1)
    logistic = 1 / (1 + np.exp(-x))
    return (logistic - logistic[0]) / (logistic[-1] - logistic[0])


def build_warehouse_schedule(deal: Deal | None = None) -> pd.DataFrame:
    deal = deal or load_deal()
    w = config.ANATOMY_WAREHOUSE
    n_quarters = w["takeout_quarter"] - w["ramp_start_quarter"]
    cum_frac = _s_curve_ramp(n_quarters)
    quarters = list(range(w["ramp_start_quarter"], w["takeout_quarter"] + 1))

    target_par = w["target_ramp_par"]
    cum_par = cum_frac * target_par
    advance_rate = w["advance_rate_pct"] / 100

    rows = []
    for i, q in enumerate(quarters):
        par = cum_par[i]
        debt_drawn = par * advance_rate
        equity_at_risk = par - debt_drawn
        # Quarterly carry on the ramped balance: loans earn SOFR+WAS,
        # warehouse debt costs SOFR+warehouse spread — the SOFR legs cancel,
        # leaving a spread-only carry (the standard warehouse-arb framing).
        quarterly_par_earning = cum_par[i - 1] if i > 0 else 0.0
        loan_income = quarterly_par_earning * (w["loan_yield_bps_over_sofr"] / 100) / 100 / 4
        debt_cost = (quarterly_par_earning * advance_rate) * (w["spread_bps_over_sofr"] / 100) / 100 / 4
        net_carry_to_equity = loan_income - debt_cost
        rows.append(dict(
            quarter=q, cumulative_par=par, warehouse_debt_drawn=debt_drawn,
            equity_at_risk=equity_at_risk, net_carry_to_equity=net_carry_to_equity,
        ))
    df = pd.DataFrame(rows)
    df["cumulative_net_carry"] = df["net_carry_to_equity"].cumsum()

    max_equity_at_risk = df["equity_at_risk"].max()
    clo_equity_size = deal.tranche("equity").size
    df.attrs["max_equity_at_risk"] = max_equity_at_risk
    df.attrs["clo_equity_size"] = clo_equity_size
    df.attrs["equity_at_risk_pct_of_clo_equity"] = 100 * max_equity_at_risk / clo_equity_size
    df.attrs["total_ramp_carry_to_equity"] = df["net_carry_to_equity"].sum()
    return df


def main():
    deal = load_deal()
    df = build_warehouse_schedule(deal)
    print(df.to_string(index=False))
    print(f"\nPeak warehouse equity at risk: ${df.attrs['max_equity_at_risk']:,.0f} "
          f"({df.attrs['equity_at_risk_pct_of_clo_equity']:.1f}% of the eventual CLO equity tranche size)")
    print(f"Total carry earned by warehouse equity during ramp: ${df.attrs['total_ramp_carry_to_equity']:,.0f}")

    out_path = config.FINAL_DIR / "anatomy" / "warehouse_schedule.parquet"
    write_parquet(df, out_path, Provenance(
        source_urls=[deal.citation.get("source_url", "")],
        parser="src.anatomy.analysis_warehouse.build_warehouse_schedule",
        notes="Model-driven, not scrape-driven: warehouse advance rate, financing spread, and ramp shape are "
              "market-standard conventions (config.ANATOMY_WAREHOUSE), not circular figures. TO-VERIFY throughout.",
    ))
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
