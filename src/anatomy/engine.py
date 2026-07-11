"""The CLO cash-flow waterfall engine — pure functions, no I/O, quarterly
periods. This is the section's highest-accuracy-bar module: every
invariant it must satisfy is enforced in `tests_engine.py`, and per this
section's hard rules, a failing golden test means the engine is wrong, not
the test.

**Model simplifications** (restated on every exhibit, listed here as the
canonical list):
  - Single currency (USD), quarterly periods, no day-count nuance beyond /4.
  - No interest-rate hedges (a stub SOFR path only).
  - Defaulted-asset carrying value = par x assumed recovery rate exactly
    (i.e., "market value" of a defaulted asset is modeled as identical to
    its assumed ultimate recovery — real deals mark defaulted assets to an
    independently volatile market price before recovery is realized; this
    project does not model that separate price process).
  - Recoveries realize on a fixed 2-quarter lag from default (a single
    lag, not a cohort-by-cohort recovery-timing distribution).
  - CCC bucket level is a direct scenario input (a migration-path
    assumption), not modeled from issuer-level rating-transition dynamics.
  - Excess-CCC (over the 7.5% basket) is haircut to a flat assumed market
    value (`CCC_EXCESS_MARKET_VALUE_PCT`), not a modeled distressed price.
  - No scheduled amortization on the underlying loans beyond CPR-driven
    unscheduled prepayment (standard for BSL loan collateral at this level
    of stylization).
  - The equity incentive-fee hurdle is modeled as a compounding "hurdle
    balance" (grows at the hurdle IRR, reduced by pre-incentive-fee equity
    distributions) rather than a full IRR solve on the realized cash-flow
    stream — a standard simplification for a forward-looking model where
    the true realized IRR isn't known until the deal is fully wound down.
  - A single failing coverage test's cure (senior-most-first principal
    paydown from interest proceeds) is checked level-by-level from AA-level
    down to BB-level, recomputing ratios after each cure — this matches
    real priority-of-payments drafting (each level's own test, in order)
    and, as a side effect, senior paydown to cure a junior test typically
    also cures every more-senior test (smaller senior-stack denominator
    helps every class simultaneously).
"""
from __future__ import annotations

from dataclasses import dataclass

from src.anatomy.deal import Deal

RECOVERY_LAG_QUARTERS = 2
CCC_EXCESS_MARKET_VALUE_PCT = 80.0  # TO-VERIFY: convention, not from the circular

TRANCHE_ORDER = ["AAA", "AA", "A", "BBB", "BB", "equity"]
# Which named test level a tranche's own coverage test is measured at (the
# circular states triggers jointly for "A/B" -> this project's AAA & AA).
TEST_LEVEL_FOR_TRANCHE = {"AAA": "AA", "AA": "AA", "A": "A", "BBB": "BBB", "BB": "BB"}
# Test levels in seniority order (most senior first) — the order coverage
# tests are checked and cured in, per the waterfall.
TEST_LEVELS_IN_ORDER = ["AA", "A", "BBB", "BB"]


@dataclass
class WaterfallStop:
    """One line of the interest or principal waterfall for one period —
    the tidy unit both the engine's invariant tests and every viz module
    consume."""
    name: str
    category: str  # "interest" or "principal"
    amount: float


@dataclass
class PeriodState:
    """Balances carried from the end of one period into the start of the
    next — the engine's only mutable state, threaded through pure
    functions rather than held on an object with methods."""
    period: int
    performing_par: float
    ccc_par: float
    defaulted_pending: list[tuple[int, float, float]]  # (quarter_defaulted, par, recovery_rate)
    tranche_balances: dict[str, float]
    equity_hurdle_balance: float


@dataclass
class PeriodResult:
    period: int
    sofr_pct: float
    cdr_pct: float
    cpr_pct: float
    recovery_rate_pct: float
    performing_par_begin: float
    new_defaults: float
    recoveries: float
    prepayments: float
    ccc_par: float
    ccc_excess: float
    adjusted_collateral_principal: float
    interest_collections: float
    oc_ratios: dict[str, float]
    ic_ratios: dict[str, float]
    oc_pass: dict[str, bool]
    ic_pass: dict[str, bool]
    interest_diversion_pass: bool
    reinvesting: bool
    waterfall_stops: list[WaterfallStop]
    tranche_balances_end: dict[str, float]
    equity_distribution: float
    total_interest_in: float
    total_principal_in: float
    total_cash_out: float  # sum of all waterfall stops, must equal total_interest_in + total_principal_in


def quarterly_rate(annual_rate_pct: float) -> float:
    """Compound annual rate -> quarterly rate: 1-(1-r)^0.25 for decay rates
    (CDR/CPR), used consistently so a 20% CPR doesn't imply exactly 5%/quarter."""
    r = annual_rate_pct / 100
    return 1 - (1 - r) ** 0.25


def initial_state(deal: Deal) -> PeriodState:
    balances = {t.name: t.size for t in deal.tranches}
    return PeriodState(
        # Collateral principal at closing = rated debt proceeds + equity
        # proceeds, all deployed to purchase the initial portfolio (equity
        # is risk capital that buys collateral alongside the notes, not a
        # side cushion held back in cash) — so performing_par starts at the
        # full target par, giving the realistic ~130%+ initial OC cushion
        # real deals close with.
        period=-1, performing_par=deal.target_par,
        ccc_par=0.0, defaulted_pending=[], tranche_balances=balances,
        equity_hurdle_balance=deal.tranche("equity").size,
    )


def _senior_stack_balance(deal: Deal, balances: dict[str, float], test_level: str) -> float:
    """Sum of balances for `test_level` and everything senior to it."""
    return sum(balances[t.name] for t in deal.senior_or_equal(test_level) if t.name in balances)


def oc_ratio(adjusted_collateral_principal: float, deal: Deal, balances: dict[str, float], test_level: str) -> float:
    denom = _senior_stack_balance(deal, balances, test_level)
    return (adjusted_collateral_principal / denom * 100) if denom else float("inf")


def ic_ratio(interest_collections: float, deal: Deal, balances_begin: dict[str, float], sofr_pct: float, test_level: str) -> float:
    interest_due = sum(
        balances_begin[t.name] * (sofr_pct + t.spread_bps / 100) / 100 / 4
        for t in deal.senior_or_equal(test_level) if t.spread_bps is not None
    )
    return (interest_collections / interest_due * 100) if interest_due else float("inf")


def adjusted_collateral_principal(deal: Deal, performing_par: float, ccc_par: float,
                                    defaulted_pending: list[tuple[int, float, float]]) -> tuple[float, float]:
    """Returns (adjusted_collateral_principal, ccc_excess_par). Excess-CCC
    (over the 7.5% basket, based on performing par) is haircut to
    CCC_EXCESS_MARKET_VALUE_PCT; defaulted assets pending recovery are
    carried at par x recovery rate (see module docstring)."""
    ccc_limit_amount = deal.ccc_limit_pct / 100 * performing_par
    ccc_excess = max(0.0, ccc_par - ccc_limit_amount)
    haircut_loss = ccc_excess * (1 - CCC_EXCESS_MARKET_VALUE_PCT / 100) if deal.ccc_haircut_to_market_value else 0.0
    defaulted_carrying_value = sum(par * recovery / 100 for _, par, recovery in defaulted_pending)
    adjusted = performing_par - haircut_loss + defaulted_carrying_value
    return adjusted, ccc_excess


def _cure_via_senior_paydown(deal: Deal, balances: dict[str, float], cash_available: float,
                              adjusted_collateral: float, test_level: str, target_ratio: float) -> tuple[float, dict[str, float]]:
    """Pay down AAA first (then AA, ... down to but not including
    `test_level`) using up to `cash_available` until the OC ratio at
    `test_level` reaches `target_ratio` or cash runs out. Returns (cash
    spent, updated balances)."""
    # Paydown always starts at the single most senior class (AAA) and
    # cascades down, regardless of which level's test triggered the cure —
    # this matches real priority-of-payments drafting.
    balances = dict(balances)
    paydown_order = [t.name for t in deal.debt_tranches if t.name in balances]
    spent = 0.0
    remaining_cash = cash_available
    for name in paydown_order:
        current_ratio = oc_ratio(adjusted_collateral, deal, balances, test_level)
        if current_ratio >= target_ratio or remaining_cash <= 0:
            break
        denom_now = _senior_stack_balance(deal, balances, test_level)
        # Amount to pay down `name` so that denom shrinks enough to hit target_ratio:
        # adjusted / (denom_now - paydown) = target/100  =>  paydown = denom_now - adjusted*100/target
        needed_denom = adjusted_collateral * 100 / target_ratio
        paydown_needed_total = max(0.0, denom_now - needed_denom)
        paydown_this_tranche = min(paydown_needed_total, balances[name], remaining_cash)
        if paydown_this_tranche <= 0:
            continue
        balances[name] -= paydown_this_tranche
        spent += paydown_this_tranche
        remaining_cash -= paydown_this_tranche
    return spent, balances


def run_period(deal: Deal, state: PeriodState, sofr_pct: float, cdr_pct: float, cpr_pct: float,
               recovery_rate_pct: float, ccc_par_target: float, reinvestment_period_end: int,
               senior_expense_this_period: float) -> tuple[PeriodResult, PeriodState]:
    """Advance the engine by exactly one quarter. Pure: all randomness/
    scenario assumptions are passed in as arguments for this period."""
    period = state.period + 1
    balances_begin = dict(state.tranche_balances)
    performing_par_begin = state.performing_par

    # --- Collateral roll-forward -----------------------------------------
    q_cdr = quarterly_rate(cdr_pct)
    q_cpr = quarterly_rate(cpr_pct)
    new_defaults = performing_par_begin * q_cdr
    performing_after_defaults = performing_par_begin - new_defaults

    defaulted_pending = list(state.defaulted_pending) + [(period, new_defaults, recovery_rate_pct)]
    recoveries = 0.0
    still_pending = []
    for q_defaulted, par, rate in defaulted_pending:
        if period - q_defaulted >= RECOVERY_LAG_QUARTERS:
            recoveries += par * rate / 100
        else:
            still_pending.append((q_defaulted, par, rate))

    prepayments = performing_after_defaults * q_cpr
    performing_par_after_collections = performing_after_defaults - prepayments

    ccc_par = min(ccc_par_target, performing_par_after_collections)

    # --- Interest accrual (on begin-of-period performing par) -------------
    interest_collections = performing_par_begin * (sofr_pct + deal.was_bps_over_sofr / 100) / 100 / 4

    adj_collateral, ccc_excess = adjusted_collateral_principal(deal, performing_par_after_collections, ccc_par, still_pending)
    # Principal proceeds collected this period (prepayments + realized
    # recoveries) sit in the principal collection account, still uninvested
    # at the moment tests are measured — they count toward the Adjusted
    # Collateral Principal Amount exactly like standard CLO indentures
    # (cash pending reinvestment/distribution is collateral, just not in
    # loan form yet). Omitting this made the OC ratio swing with CPR alone.
    adj_collateral += prepayments + recoveries

    # --- Interest waterfall ------------------------------------------------
    stops: list[WaterfallStop] = []
    balances = dict(balances_begin)
    cash = interest_collections

    def pay(name: str, amount: float, category: str = "interest") -> float:
        nonlocal cash
        paid = max(0.0, min(amount, cash))
        cash -= paid
        stops.append(WaterfallStop(name=name, category=category, amount=paid))
        return paid

    pay("senior_expenses", senior_expense_this_period)
    pay("senior_mgmt_fee", performing_par_begin * deal.senior_mgmt_fee_pct / 100 / 4)

    # AAA sits senior to the first coverage-test level (AA, per the
    # circular's joint "A/B" trigger) and is paid before any test is
    # checked. AAA is not PIK-able (deal.py), so a real deficiency here
    # would be an Event of Default in an actual deal — not modeled (see
    # module docstring's simplifications list); every scenario in this
    # project keeps AAA money-good, so this stays a live but dormant edge case.
    aaa = deal.tranche("AAA")
    aaa_due = balances_begin["AAA"] * (sofr_pct + aaa.spread_bps / 100) / 100 / 4
    pay("AAA_interest", aaa_due)

    oc_ratios, ic_ratios, oc_pass, ic_pass = {}, {}, {}, {}
    for level in TEST_LEVELS_IN_ORDER:
        tranche = deal.tranche(level)
        due = balances_begin[level] * (sofr_pct + tranche.spread_bps / 100) / 100 / 4
        paid = pay(f"{level}_interest", due)
        if paid < due and tranche.pikable:
            balances[level] += due - paid  # capitalize deferred interest onto principal

        oc = oc_ratio(adj_collateral, deal, balances, level)
        ic = ic_ratio(interest_collections, deal, balances_begin, sofr_pct, level) if level != "BB" else float("inf")
        oc_target = deal.oc_triggers_pct[level]
        ic_target = deal.ic_triggers_pct.get(level, 0.0)
        passing = oc >= oc_target and (level == "BB" or ic >= ic_target)
        if not passing:
            spent, balances = _cure_via_senior_paydown(deal, balances, cash, adj_collateral, level, oc_target)
            cash -= spent
            stops.append(WaterfallStop(name=f"divert_to_{level}_cure", category="interest_diversion", amount=spent))
            oc = oc_ratio(adj_collateral, deal, balances, level)
            ic = ic_ratio(interest_collections, deal, balances_begin, sofr_pct, level) if level != "BB" else float("inf")
            passing = oc >= oc_target and (level == "BB" or ic >= ic_target)
        oc_ratios[level] = oc
        ic_ratios[level] = ic
        oc_pass[level] = passing
        ic_pass[level] = (ic >= ic_target) if level != "BB" else True

    reinvesting = period <= reinvestment_period_end and all(oc_pass.values())

    bb_oc_for_diversion = oc_ratio(adj_collateral, deal, balances, "BB")
    interest_diversion_pass = bb_oc_for_diversion >= deal.interest_diversion_trigger_pct
    diverted_to_principal = 0.0
    if period <= reinvestment_period_end and not interest_diversion_pass:
        half_remaining = 0.5 * cash
        # Cash needed to bring BB OC to trigger, treating the diversion as
        # if it were added to adjusted_collateral (reinvested as principal,
        # which raises the OC numerator directly rather than shrinking a
        # denominator):
        denom = _senior_stack_balance(deal, balances, "BB")
        needed = max(0.0, (deal.interest_diversion_trigger_pct / 100 * denom) - adj_collateral)
        diverted_to_principal = min(half_remaining, needed, cash)
        cash -= diverted_to_principal
        stops.append(WaterfallStop(name="interest_diversion_test", category="interest_diversion", amount=diverted_to_principal))

    pay("sub_mgmt_fee", performing_par_begin * deal.sub_mgmt_fee_pct / 100 / 4)

    hurdle_growth = state.equity_hurdle_balance * (deal.incentive_hurdle_irr_pct / 100 / 4)
    equity_hurdle_balance = state.equity_hurdle_balance + hurdle_growth
    if equity_hurdle_balance <= 0 and cash > 0:
        pay("incentive_fee", cash * deal.incentive_fee_pct / 100)
    residual_to_equity_interest = cash
    pay("equity_residual_interest", residual_to_equity_interest)
    equity_hurdle_balance = max(0.0, equity_hurdle_balance - residual_to_equity_interest)

    # --- Principal waterfall ------------------------------------------------
    principal_available = prepayments + recoveries + diverted_to_principal
    principal_cash = principal_available
    equity_distribution_principal = 0.0

    if reinvesting:
        performing_par_end = performing_par_after_collections + principal_cash
        stops.append(WaterfallStop(name="principal_reinvested", category="principal", amount=principal_cash))
        principal_cash = 0.0
    else:
        performing_par_end = performing_par_after_collections
        for name in [t.name for t in deal.debt_tranches]:
            if principal_cash <= 0:
                break
            paydown = min(balances[name], principal_cash)
            balances[name] -= paydown
            principal_cash -= paydown
            stops.append(WaterfallStop(name=f"{name}_principal", category="principal", amount=paydown))
        if principal_cash > 0:
            equity_distribution_principal = principal_cash
            stops.append(WaterfallStop(name="equity_residual_principal", category="principal", amount=principal_cash))
            principal_cash = 0.0

    equity_distribution = residual_to_equity_interest + equity_distribution_principal

    total_interest_in = interest_collections
    total_principal_in = principal_available
    total_cash_out = sum(s.amount for s in stops)

    result = PeriodResult(
        period=period, sofr_pct=sofr_pct, cdr_pct=cdr_pct, cpr_pct=cpr_pct, recovery_rate_pct=recovery_rate_pct,
        performing_par_begin=performing_par_begin, new_defaults=new_defaults, recoveries=recoveries,
        prepayments=prepayments, ccc_par=ccc_par, ccc_excess=ccc_excess, adjusted_collateral_principal=adj_collateral,
        interest_collections=interest_collections, oc_ratios=oc_ratios, ic_ratios=ic_ratios,
        oc_pass=oc_pass, ic_pass=ic_pass, interest_diversion_pass=interest_diversion_pass, reinvesting=reinvesting,
        waterfall_stops=stops, tranche_balances_end=dict(balances), equity_distribution=equity_distribution,
        total_interest_in=total_interest_in, total_principal_in=total_principal_in, total_cash_out=total_cash_out,
    )
    new_state = PeriodState(
        period=period, performing_par=performing_par_end, ccc_par=ccc_par, defaulted_pending=still_pending,
        tranche_balances=balances, equity_hurdle_balance=equity_hurdle_balance,
    )
    return result, new_state
