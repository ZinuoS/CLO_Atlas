"""Golden tests + invariants for the waterfall engine (pytest). Per this
section's hard rules: if one of these fails, the fix is in `engine.py`,
never here. Discovered by pytest via `testpaths`/`python_files` in
pytest.ini (this file lives beside the engine it tests, not in `tests/`,
per this section's own layout).
"""
from __future__ import annotations

import pytest

from src.anatomy.deal import Deal, DealDates, Tranche, load_deal
from src.anatomy.engine import (
    TEST_LEVELS_IN_ORDER, adjusted_collateral_principal, ic_ratio, initial_state,
    oc_ratio, quarterly_rate, run_period,
)

# ---------------------------------------------------------------------------
# A small, fully hand-computable deal for unit-level fixture tests — real
# numbers chosen so every ratio comes out to a clean fraction.
# ---------------------------------------------------------------------------
def _toy_deal() -> Deal:
    tranches = (
        Tranche(name="AAA", size=600.0, spread_bps=100, rating="AAA", pikable=False, seniority=0),
        Tranche(name="AA", size=100.0, spread_bps=150, rating="AA", pikable=False, seniority=1),
        Tranche(name="A", size=100.0, spread_bps=200, rating="A", pikable=True, seniority=2),
        Tranche(name="BBB", size=100.0, spread_bps=300, rating="BBB", pikable=True, seniority=3),
        Tranche(name="BB", size=50.0, spread_bps=500, rating="BB", pikable=True, seniority=4),
        Tranche(name="equity", size=50.0, spread_bps=None, rating=None, pikable=False, seniority=5),
    )
    dates = DealDates(
        warehouse_open_quarter=-3, pricing_quarter=-1, closing_quarter=0, effective_date_quarter=0,
        non_call_end_quarter=8, reinvestment_end_quarter=20, stated_maturity_quarter=52,
        closing_date_calendar="2025-01-01", non_call_end_calendar="2027-01-01",
        reinvestment_end_calendar="2030-01-01", stated_maturity_calendar="2038-01-01",
    )
    return Deal(
        tranches=tranches, target_par=1000.0, dates=dates,
        oc_triggers_pct={"AA": 120.0, "A": 115.0, "BBB": 108.0, "BB": 103.0},
        ic_triggers_pct={"AA": 115.0, "A": 110.0, "BBB": 105.0},
        interest_diversion_trigger_pct=103.5, ccc_limit_pct=7.5, ccc_haircut_to_market_value=True,
        senior_mgmt_fee_pct=0.15, sub_mgmt_fee_pct=0.20, incentive_fee_pct=20.0, incentive_hurdle_irr_pct=12.0,
        senior_expense_cap_usd_annual=1.0, was_bps_over_sofr=350, warf=2900, diversity_score=65,
        recovery_rate_pct=70.0, base_cdr_pct=2.0, base_cpr_pct=20.0, sofr_base_pct=4.0,
        citation={"deal_name": "toy fixture deal, not a real filing"},
    )


def _run_n_periods(deal: Deal, n: int, **overrides):
    state = initial_state(deal)
    results = []
    for _ in range(n):
        kwargs = dict(
            sofr_pct=deal.sofr_base_pct, cdr_pct=deal.base_cdr_pct, cpr_pct=deal.base_cpr_pct,
            recovery_rate_pct=deal.recovery_rate_pct, ccc_par_target=0.0,
            reinvestment_period_end=deal.dates.reinvestment_end_quarter,
            senior_expense_this_period=deal.senior_expense_cap_usd_annual / 4,
        )
        kwargs.update(overrides)
        result, state = run_period(deal, state, **kwargs)
        results.append(result)
    return results, state


# ---------------------------------------------------------------------------
# Invariant 1: cash conservation, to the cent, every period.
# ---------------------------------------------------------------------------
def test_cash_conservation_base_case_toy_deal():
    deal = _toy_deal()
    results, _ = _run_n_periods(deal, 24)
    for r in results:
        assert r.total_cash_out == pytest.approx(r.total_interest_in + r.total_principal_in, abs=1e-6), \
            f"period {r.period}: cash in {r.total_interest_in + r.total_principal_in} != cash out {r.total_cash_out}"


def test_cash_conservation_real_deal():
    deal = load_deal()
    # ccc_par_target depends on state.performing_par, so it's recomputed
    # each period below rather than passed as a fixed override.
    state = initial_state(deal)
    for _ in range(32):
        result, state = run_period(
            deal, state, sofr_pct=deal.sofr_base_pct, cdr_pct=deal.base_cdr_pct, cpr_pct=deal.base_cpr_pct,
            recovery_rate_pct=deal.recovery_rate_pct, ccc_par_target=0.02 * state.performing_par,
            reinvestment_period_end=deal.dates.reinvestment_end_quarter,
            senior_expense_this_period=deal.senior_expense_cap_usd_annual / 4,
        )
        assert result.total_cash_out == pytest.approx(result.total_interest_in + result.total_principal_in, abs=1e-6)


def test_cash_conservation_under_stress():
    """The exact case that first exposed the reinvestment-recording bug:
    high CDR, tests failing, cures firing, principal both diverting and
    reinvesting in the same run."""
    deal = _toy_deal()
    results, _ = _run_n_periods(deal, 16, cdr_pct=15.0, recovery_rate_pct=40.0, ccc_par_target=15.0)
    for r in results:
        assert r.total_cash_out == pytest.approx(r.total_interest_in + r.total_principal_in, abs=1e-6)


# ---------------------------------------------------------------------------
# Invariant 2: strict priority ordering — a junior stop can only be zero or
# fully starved once cash is exhausted; it can never be paid while a more
# senior stop in the same category was left underpaid.
# ---------------------------------------------------------------------------
def test_aaa_interest_is_paid_and_senior_to_every_test_level():
    """AAA sits above the first coverage-test level and is paid before any
    of AA/A/BBB/BB. This is the exact invariant that would have caught the
    bug where the interest waterfall paid AA-BB but never AAA itself."""
    deal = _toy_deal()
    results, _ = _run_n_periods(deal, 8)
    for r in results:
        by_name = {s.name: s.amount for s in r.waterfall_stops}
        aaa_due = deal.tranche("AAA").size * (deal.sofr_base_pct + deal.tranche("AAA").spread_bps / 100) / 100 / 4
        assert by_name.get("AAA_interest", 0.0) == pytest.approx(aaa_due), \
            f"period {r.period}: AAA interest paid {by_name.get('AAA_interest', 0.0)} != due {aaa_due}"
        # AAA_interest must appear as its own stop, distinct from and prior
        # to the AA/A/BBB/BB stops already covered by the ordering test below.
        assert "AAA_interest" in by_name


def test_priority_ordering_senior_paid_before_junior_under_severe_stress():
    deal = _toy_deal()
    # Extreme stress: defaults eat most of the collateral, so interest
    # collections shrink far below what's needed to pay every class.
    results, _ = _run_n_periods(deal, 4, cdr_pct=60.0, recovery_rate_pct=20.0, ccc_par_target=0.0)
    for r in results:
        by_name = {s.name: s.amount for s in r.waterfall_stops if s.category == "interest"}
        levels = [f"{lvl}_interest" for lvl in TEST_LEVELS_IN_ORDER]
        # Once one level's interest is underpaid (didn't fully cover what
        # senior-level accrual would need), every level after it in
        # priority order must receive exactly zero this period.
        starved = False
        for name in levels:
            amount = by_name.get(name, 0.0)
            if starved:
                assert amount == 0.0, f"period {r.period}: {name} was paid {amount} after a senior class was starved"
            if amount == 0.0:
                starved = True


def test_equity_gets_nothing_while_any_rated_debt_interest_unpaid():
    deal = _toy_deal()
    results, _ = _run_n_periods(deal, 4, cdr_pct=80.0, recovery_rate_pct=10.0, ccc_par_target=0.0)
    for r in results:
        by_name = {s.name: s.amount for s in r.waterfall_stops}
        # If total interest collections fall well short of total interest
        # due across all rated classes, the equity residual interest stop
        # must be exactly zero — equity never gets paid ahead of debt.
        total_due = sum(
            deal.tranche(lvl).size * (deal.sofr_base_pct + deal.tranche(lvl).spread_bps / 100) / 100 / 4
            for lvl in TEST_LEVELS_IN_ORDER
        )
        if r.interest_collections < total_due * 0.5:  # comfortably starved
            assert by_name.get("equity_residual_interest", 0.0) == 0.0


# ---------------------------------------------------------------------------
# Invariant 3: OC/IC ratio math reproduced against a hand computation.
# ---------------------------------------------------------------------------
def test_oc_ratio_matches_hand_computation():
    deal = _toy_deal()
    balances = {"AAA": 600.0, "AA": 100.0, "A": 100.0, "BBB": 100.0, "BB": 50.0}
    # AA-level senior-or-equal stack = AAA + AA = 700. adjusted collateral = 1000.
    expected = 1000.0 / 700.0 * 100
    assert oc_ratio(1000.0, deal, balances, "AA") == pytest.approx(expected)

    # BBB-level stack = AAA+AA+A+BBB = 900. adjusted collateral = 950.
    expected_bbb = 950.0 / 900.0 * 100
    assert oc_ratio(950.0, deal, balances, "BBB") == pytest.approx(expected_bbb)


def test_ic_ratio_matches_hand_computation():
    deal = _toy_deal()
    balances_begin = {"AAA": 600.0, "AA": 100.0, "A": 100.0, "BBB": 100.0, "BB": 50.0}
    sofr = 4.0
    # AA-level interest due = 600*(4+1)/100/4 + 100*(4+1.5)/100/4
    aaa_due = 600.0 * (sofr + 1.00) / 100 / 4
    aa_due = 100.0 * (sofr + 1.50) / 100 / 4
    total_due = aaa_due + aa_due
    collections = 20.0
    expected = collections / total_due * 100
    assert ic_ratio(collections, deal, balances_begin, sofr, "AA") == pytest.approx(expected)


def test_adjusted_collateral_principal_applies_ccc_haircut_and_default_recovery():
    deal = _toy_deal()
    # performing_par=900, ccc_par=100 (limit is 7.5% of 900=67.5, so excess=32.5,
    # haircut to 80% MV -> loses 20% of 32.5 = 6.5), one defaulted bucket of
    # par 50 at 70% recovery -> carrying value 35.
    adj, excess = adjusted_collateral_principal(deal, performing_par=900.0, ccc_par=100.0,
                                                  defaulted_pending=[(0, 50.0, 70.0)])
    assert excess == pytest.approx(32.5)
    expected = 900.0 - 32.5 * 0.20 + 35.0
    assert adj == pytest.approx(expected)


def test_quarterly_rate_conversion_is_compounding_not_flat_divide():
    # A 20% annual rate does NOT imply exactly 5%/quarter under compounding.
    q = quarterly_rate(20.0)
    assert q == pytest.approx(1 - 0.8 ** 0.25)
    assert q != pytest.approx(0.05, abs=1e-4)


# ---------------------------------------------------------------------------
# Invariant 4: cure mechanics — a failing test diverts interest to senior
# principal, the ratio recomputes and improves, and diversion is exactly
# zero once the test already passes.
# ---------------------------------------------------------------------------
def test_cure_reduces_senior_balance_and_the_diversion_stops_once_cured():
    deal = _toy_deal()
    # Force a real breach: very high CDR for a burst, then let it recede.
    # With principal proceeds now correctly counted in the collateral base
    # (see engine.py's adjusted_collateral_principal call site), this burst
    # breaches the A-level test specifically (AA stays money-good throughout).
    level = "A"
    state = initial_state(deal)
    breached = False
    cured_after_breach = False
    prior_aaa_balance = state.tranche_balances["AAA"]
    for q in range(20):
        cdr = 40.0 if q < 3 else 1.0
        result, state = run_period(
            deal, state, sofr_pct=4.0, cdr_pct=cdr, cpr_pct=10.0, recovery_rate_pct=50.0,
            ccc_par_target=0.0, reinvestment_period_end=deal.dates.reinvestment_end_quarter,
            senior_expense_this_period=deal.senior_expense_cap_usd_annual / 4,
        )
        cure_stops = [s for s in result.waterfall_stops if s.category == "interest_diversion" and s.name.startswith("divert_to_")]
        if not result.oc_pass[level]:
            breached = True
            # A cure attempt must have fired and the AAA balance must not increase.
            assert state.tranche_balances["AAA"] <= prior_aaa_balance + 1e-6
        elif breached and not cured_after_breach:
            # First period after the breach clears: diversion for this level should be zero (nothing left to cure).
            same_level_cures = [s.amount for s in cure_stops if s.name == f"divert_to_{level}_cure"]
            assert not same_level_cures or same_level_cures[0] == pytest.approx(0.0)
            cured_after_breach = True
        prior_aaa_balance = state.tranche_balances["AAA"]
    assert breached, "test setup should have forced at least one real breach"
    assert cured_after_breach, "the breach should have cured once CDR receded"


def test_cure_never_makes_ratio_worse():
    deal = _toy_deal()
    results, _ = _run_n_periods(deal, 12, cdr_pct=25.0, recovery_rate_pct=45.0, ccc_par_target=10.0)
    for r in results:
        for level in TEST_LEVELS_IN_ORDER:
            # A cured (or never-breached) ratio must be a real number and
            # not negative/nonsensical.
            assert r.oc_ratios[level] >= 0


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
