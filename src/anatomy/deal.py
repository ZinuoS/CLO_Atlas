"""Stylized CLO deal spec: dataclasses loaded from config.ANATOMY_DEAL —
the single, hand-approved source of truth (see config.py's ANATOMY_DEAL
docstring for exactly which fields are cited to the public offering
circular vs. market-standard convention).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import config


@dataclass(frozen=True)
class Tranche:
    name: str
    size: float
    spread_bps: float | None  # None for equity
    rating: str | None
    pikable: bool
    seniority: int  # 0 = most senior


@dataclass(frozen=True)
class DealDates:
    warehouse_open_quarter: int
    pricing_quarter: int
    closing_quarter: int
    effective_date_quarter: int
    non_call_end_quarter: int
    reinvestment_end_quarter: int
    stated_maturity_quarter: int
    closing_date_calendar: str
    non_call_end_calendar: str
    reinvestment_end_calendar: str
    stated_maturity_calendar: str


@dataclass(frozen=True)
class Deal:
    tranches: tuple[Tranche, ...]
    target_par: float
    dates: DealDates
    oc_triggers_pct: dict[str, float]
    ic_triggers_pct: dict[str, float]
    interest_diversion_trigger_pct: float
    ccc_limit_pct: float
    ccc_haircut_to_market_value: bool
    senior_mgmt_fee_pct: float
    sub_mgmt_fee_pct: float
    incentive_fee_pct: float
    incentive_hurdle_irr_pct: float
    senior_expense_cap_usd_annual: float
    was_bps_over_sofr: float
    warf: float
    diversity_score: float
    recovery_rate_pct: float
    base_cdr_pct: float
    base_cpr_pct: float
    sofr_base_pct: float
    citation: dict = field(default_factory=lambda: dict(config.ANATOMY_CIRCULAR_CITATION))

    def tranche(self, name: str) -> Tranche:
        for t in self.tranches:
            if t.name == name:
                return t
        raise KeyError(f"no tranche named {name!r}")

    @property
    def debt_tranches(self) -> tuple[Tranche, ...]:
        """All tranches except equity, in seniority order."""
        return tuple(t for t in self.tranches if t.name != "equity")

    @property
    def rated_debt_par(self) -> float:
        return sum(t.size for t in self.debt_tranches)

    def senior_or_equal(self, name: str) -> tuple[Tranche, ...]:
        """This tranche and everything senior to it (for OC/IC denominators)."""
        target = self.tranche(name)
        return tuple(t for t in self.debt_tranches if t.seniority <= target.seniority)


def load_deal(params: dict | None = None) -> Deal:
    params = params or config.ANATOMY_DEAL
    tranches = tuple(
        Tranche(name=t["name"], size=t["size"], spread_bps=t["spread_bps"], rating=t["rating"],
                pikable=t["pikable"], seniority=i)
        for i, t in enumerate(params["tranches"])
    )
    dates = DealDates(**params["dates"])
    return Deal(
        tranches=tranches, target_par=params["target_par"], dates=dates,
        oc_triggers_pct=dict(params["oc_triggers_pct"]), ic_triggers_pct=dict(params["ic_triggers_pct"]),
        interest_diversion_trigger_pct=params["interest_diversion_trigger_pct"],
        ccc_limit_pct=params["ccc_limit_pct"], ccc_haircut_to_market_value=params["ccc_haircut_to_market_value"],
        senior_mgmt_fee_pct=params["senior_mgmt_fee_pct"], sub_mgmt_fee_pct=params["sub_mgmt_fee_pct"],
        incentive_fee_pct=params["incentive_fee_pct"], incentive_hurdle_irr_pct=params["incentive_hurdle_irr_pct"],
        senior_expense_cap_usd_annual=params["senior_expense_cap_usd_annual"],
        was_bps_over_sofr=params["was_bps_over_sofr"], warf=params["warf"], diversity_score=params["diversity_score"],
        recovery_rate_pct=params["recovery_rate_pct"], base_cdr_pct=params["base_cdr_pct"],
        base_cpr_pct=params["base_cpr_pct"], sofr_base_pct=params["sofr_base_pct"],
    )


def main():
    deal = load_deal()
    print(f"Deal: {deal.citation['deal_name']}")
    print(f"Target par: ${deal.target_par:,.0f}")
    for t in deal.tranches:
        spread = f"SOFR+{t.spread_bps}bps" if t.spread_bps else "residual"
        print(f"  {t.name:8s} ${t.size:>13,.0f}  {spread:16s} {t.rating or ''}")
    print(f"Non-call ends Q{deal.dates.non_call_end_quarter} ({deal.dates.non_call_end_calendar})")
    print(f"Reinvestment ends Q{deal.dates.reinvestment_end_quarter} ({deal.dates.reinvestment_end_calendar})")
    print(f"Stated maturity Q{deal.dates.stated_maturity_quarter} ({deal.dates.stated_maturity_calendar})")


if __name__ == "__main__":
    main()
