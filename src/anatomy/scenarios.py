"""Scenario definitions for the waterfall engine — each a named path of
(CDR, CPR, recovery, CCC share, SOFR) per quarter, plus the one-line thesis
that becomes that scenario's figure headline. CDR/CPR/recovery base-case
levels are market-standard PRICING CONVENTIONS, not this project's own
data — TO-VERIFY against desk practice, exactly as the brief specifies.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from src.anatomy.deal import Deal, load_deal
from src.anatomy.engine import PeriodResult, initial_state, run_period

N_PERIODS_FULL_LIFE = 52  # matches the deal's stated maturity in quarters


@dataclass
class Scenario:
    name: str
    thesis: str
    n_periods: int
    cdr_path: Callable[[int], float]
    cpr_path: Callable[[int], float]
    recovery_path: Callable[[int], float]
    ccc_share_path: Callable[[int], float]
    sofr_path: Callable[[int], float]


def _flat(value: float) -> Callable[[int], float]:
    return lambda period: value


def _step(base: float, shocked: float, start: int, end: int) -> Callable[[int], float]:
    """`shocked` from period `start` (inclusive) to `end` (exclusive), `base` elsewhere."""
    return lambda period: shocked if start <= period < end else base


def _ramp_then_flat(start_value: float, end_value: float, ramp_start: int, ramp_periods: int) -> Callable[[int], float]:
    def f(period: int) -> float:
        if period < ramp_start:
            return start_value
        progress = min(1.0, (period - ramp_start) / ramp_periods)
        return start_value + (end_value - start_value) * progress
    return f


def build_scenarios(deal: Deal | None = None) -> dict[str, Scenario]:
    deal = deal or load_deal()
    base_cdr, base_cpr, base_rec, base_sofr = deal.base_cdr_pct, deal.base_cpr_pct, deal.recovery_rate_pct, deal.sofr_base_pct

    scenarios: dict[str, Scenario] = {}

    scenarios["base"] = Scenario(
        name="base", thesis="In the base case, the waterfall is boring, and that is the product.",
        n_periods=N_PERIODS_FULL_LIFE,
        cdr_path=_flat(base_cdr), cpr_path=_flat(base_cpr), recovery_path=_flat(base_rec),
        ccc_share_path=_flat(2.0), sofr_path=_flat(base_sofr),
    )

    covid_start, covid_end = 2, 6  # a 4-quarter shock early in the deal's life
    scenarios["covid_shock"] = Scenario(
        name="covid_shock",
        thesis="A four-quarter default spike breaches the junior OC test, shuts off equity, and cures itself.",
        n_periods=N_PERIODS_FULL_LIFE,
        cdr_path=_step(base_cdr, 12.0, covid_start, covid_end),
        cpr_path=_step(base_cpr, 8.0, covid_start, covid_end),  # prepayments slow in a liquidity shock
        recovery_path=_step(base_rec, 55.0, covid_start, covid_end),
        ccc_share_path=_step(2.0, 18.0, covid_start, covid_end + 2),  # CCC bucket lags the default spike by a bit and de-migrates slower
        sofr_path=_flat(base_sofr),
    )

    recession_start, recession_end = 3, 13  # deeper AND longer than the COVID shock
    scenarios["severe_recession"] = Scenario(
        name="severe_recession",
        thesis="A deeper, longer downturn defers mezz interest and tests whether AAA really is money-good.",
        n_periods=N_PERIODS_FULL_LIFE,
        cdr_path=_step(base_cdr, 16.0, recession_start, recession_end),
        cpr_path=_step(base_cpr, 8.0, recession_start, recession_end),
        recovery_path=_step(base_rec, 32.0, recession_start, recession_end),
        ccc_share_path=_step(2.0, 28.0, recession_start, recession_end + 3),
        sofr_path=_flat(base_sofr),
    )

    reinvest_end = deal.dates.reinvestment_end_quarter
    scenarios["post_reinvestment_amortization"] = Scenario(
        name="post_reinvestment_amortization",
        thesis="Once reinvestment ends, fast prepayments amortize the AAA away and compress every tranche's WAL.",
        n_periods=N_PERIODS_FULL_LIFE,
        cdr_path=_flat(base_cdr), recovery_path=_flat(base_rec), ccc_share_path=_flat(2.0),
        cpr_path=_step(base_cpr, 38.0, reinvest_end, N_PERIODS_FULL_LIFE),
        sofr_path=_flat(base_sofr),
    )

    scenarios["rate_shock_up"] = Scenario(
        name="rate_shock_up", thesis="Rates ramp up: both sides of the balance sheet float — the spread, not the level, is what equity actually feels.",
        n_periods=N_PERIODS_FULL_LIFE,
        cdr_path=_flat(base_cdr), cpr_path=_flat(base_cpr), recovery_path=_flat(base_rec), ccc_share_path=_flat(2.0),
        sofr_path=_ramp_then_flat(base_sofr, base_sofr + 1.70, ramp_start=1, ramp_periods=4),
    )
    scenarios["rate_shock_down"] = Scenario(
        name="rate_shock_down", thesis="Rates ramp down: the same pass-through, in reverse — equity's residual barely moves.",
        n_periods=N_PERIODS_FULL_LIFE,
        cdr_path=_flat(base_cdr), cpr_path=_flat(base_cpr), recovery_path=_flat(base_rec), ccc_share_path=_flat(2.0),
        sofr_path=_ramp_then_flat(base_sofr, base_sofr - 2.30, ramp_start=1, ramp_periods=4),
    )

    return scenarios


def run_scenario(deal: Deal, scenario: Scenario) -> pd.DataFrame:
    """Drive the engine for `scenario.n_periods` quarters; returns a tidy
    per-period frame (one row per quarter) with every waterfall stop
    flattened into its own column, plus the ratio/state columns every viz
    module in this section reads from."""
    state = initial_state(deal)
    rows = []
    for period in range(scenario.n_periods):
        cdr = scenario.cdr_path(period)
        cpr = scenario.cpr_path(period)
        recovery = scenario.recovery_path(period)
        ccc_share = scenario.ccc_share_path(period)
        sofr = scenario.sofr_path(period)
        result, state = run_period(
            deal, state, sofr_pct=sofr, cdr_pct=cdr, cpr_pct=cpr, recovery_rate_pct=recovery,
            ccc_par_target=ccc_share / 100 * state.performing_par,
            reinvestment_period_end=deal.dates.reinvestment_end_quarter,
            senior_expense_this_period=deal.senior_expense_cap_usd_annual / 4,
        )
        rows.append(_flatten_result(result))
    return pd.DataFrame(rows)


def _flatten_result(r: PeriodResult) -> dict:
    row = {
        "period": r.period, "sofr_pct": r.sofr_pct, "cdr_pct": r.cdr_pct, "cpr_pct": r.cpr_pct,
        "recovery_rate_pct": r.recovery_rate_pct, "performing_par_begin": r.performing_par_begin,
        "new_defaults": r.new_defaults, "recoveries": r.recoveries, "prepayments": r.prepayments,
        "ccc_par": r.ccc_par, "ccc_excess": r.ccc_excess, "adjusted_collateral_principal": r.adjusted_collateral_principal,
        "interest_collections": r.interest_collections, "reinvesting": r.reinvesting,
        "interest_diversion_pass": r.interest_diversion_pass, "equity_distribution": r.equity_distribution,
        "total_interest_in": r.total_interest_in, "total_principal_in": r.total_principal_in,
        "total_cash_out": r.total_cash_out,
    }
    for level, val in r.oc_ratios.items():
        row[f"oc_ratio_{level}"] = val
        row[f"oc_pass_{level}"] = r.oc_pass[level]
    for level, val in r.ic_ratios.items():
        row[f"ic_ratio_{level}"] = val
    for name, balance in r.tranche_balances_end.items():
        row[f"balance_{name}"] = balance
    for stop in r.waterfall_stops:
        col = f"stop_{stop.category}_{stop.name}"
        row[col] = row.get(col, 0.0) + stop.amount
    return row


def main():
    deal = load_deal()
    scenarios = build_scenarios(deal)
    for key, scenario in scenarios.items():
        df = run_scenario(deal, scenario)
        print(f"{key}: {len(df)} periods, final equity cumulative dist = ${df['equity_distribution'].sum():,.0f}, "
              f"min AA OC pass = {df['oc_pass_AA'].min()}")


if __name__ == "__main__":
    main()
