"""The CLO arbitrage: the spread between what the portfolio earns and what
the liabilities cost, decomposed into fees and expected credit losses, with
the analytical (steady-state) approximation cross-checked against the
engine's own simulated base-case equity cash flow.
"""
from __future__ import annotations

import pandas as pd

import config
from src.anatomy.deal import Deal, load_deal
from src.anatomy.scenarios import build_scenarios, run_scenario
from src.common.cache import Provenance, write_parquet


def build_excess_spread_bridge(deal: Deal | None = None) -> pd.DataFrame:
    """A steady-state (single-period, base-assumption) bridge from gross
    portfolio yield down to net excess spread available to equity. This is
    an analytical approximation for intuition, not a substitute for the
    engine's actual quarter-by-quarter simulation (cross-checked in
    `main()` against the simulated base-case equity yield)."""
    deal = deal or load_deal()
    portfolio_yield_bps = deal.was_bps_over_sofr

    liability_cost_bps = sum(t.size * t.spread_bps for t in deal.debt_tranches) / deal.rated_debt_par
    # Fees + expenses expressed as bps of collateral par so they net against
    # the same "bps over SOFR" basis as the asset/liability spreads above.
    fee_bps = (deal.senior_mgmt_fee_pct + deal.sub_mgmt_fee_pct) * 100
    expense_bps = deal.senior_expense_cap_usd_annual / deal.target_par * 100 * 100
    # Expected credit loss ~ CDR x (1 - recovery), annualized — the steady-
    # state drag on the asset yield from defaults, net of recoveries.
    expected_loss_bps = deal.base_cdr_pct * (1 - deal.recovery_rate_pct / 100) * 100

    liability_cost_on_pool_bps = liability_cost_bps * deal.rated_debt_par / deal.target_par
    net_excess_spread_bps = portfolio_yield_bps - liability_cost_on_pool_bps - fee_bps - expense_bps - expected_loss_bps

    rows = [
        dict(step="Portfolio yield (WAS over SOFR)", bps=portfolio_yield_bps),
        dict(step="- Liability cost (blended debt coupon, on pool)", bps=-liability_cost_on_pool_bps),
        dict(step="- Management fees (senior + sub)", bps=-fee_bps),
        dict(step="- Senior expenses cap", bps=-expense_bps),
        dict(step="- Expected credit losses (base CDR x loss severity)", bps=-expected_loss_bps),
        dict(step="= Net excess spread to equity", bps=net_excess_spread_bps),
    ]
    df = pd.DataFrame(rows)
    df.attrs["net_excess_spread_bps"] = net_excess_spread_bps
    df.attrs["equity_size"] = deal.tranche("equity").size
    # net_excess_spread_bps is bps of the whole collateral pool; converting
    # to a percent (÷100) and then re-basing from pool size to equity size
    # (×target_par/equity_size) gives the annualized yield that spread
    # implies on the equity check alone.
    df.attrs["implied_equity_yield_pct"] = (net_excess_spread_bps / 100) * (deal.target_par / deal.tranche("equity").size)
    return df


def simulated_base_case_equity_yield_pct(deal: Deal | None = None) -> float:
    """Cross-check: the engine's own simulated base-case annualized cash
    yield to equity, for comparison against the analytical bridge above."""
    deal = deal or load_deal()
    scenarios = build_scenarios(deal)
    df = run_scenario(deal, scenarios["base"])
    annual_distributions = df["equity_distribution"].sum() / (len(df) / 4)
    return 100 * annual_distributions / deal.tranche("equity").size


def main():
    deal = load_deal()
    bridge = run(deal)
    print(bridge.to_string(index=False))
    print(f"\nAnalytical (steady-state) implied equity yield: {bridge.attrs['implied_equity_yield_pct']:.1f}%")

    simulated_yield = simulated_base_case_equity_yield_pct(deal)
    print(f"Simulated (engine, base case) average annual equity yield: {simulated_yield:.1f}%")
    print("These will not match exactly: the analytical bridge is a static, single-period approximation; "
          "the simulation reflects the actual amortizing, sequential-paydown path over the deal's life.")


def run(deal: Deal | None = None) -> pd.DataFrame:
    deal = deal or load_deal()
    bridge = build_excess_spread_bridge(deal)
    out_path = config.FINAL_DIR / "anatomy" / "excess_spread_bridge.parquet"
    write_parquet(bridge, out_path, Provenance(
        source_urls=[deal.citation.get("source_url", "")], parser="src.anatomy.analysis_arb.build_excess_spread_bridge",
        notes="Steady-state analytical approximation (TO-VERIFY: expected-loss and fee-basis conventions), "
              "cross-checked against the engine's simulated base-case equity yield in main().",
    ))
    return bridge


if __name__ == "__main__":
    main()
