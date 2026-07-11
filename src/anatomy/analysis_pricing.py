"""Tranche-pricing anatomy: subordination (attachment/detachment), coupon,
and weighted-average life (WAL) — the terms an investor actually prices
off of — computed straight from the deal's capital structure and the
engine's own simulated principal cash flows (no separate pricing model).
"""
from __future__ import annotations

import pandas as pd

import config
from src.anatomy.deal import Deal, load_deal
from src.anatomy.engine import TRANCHE_ORDER
from src.anatomy.scenarios import build_scenarios, run_scenario
from src.common.cache import Provenance, write_parquet


def build_capital_structure_table(deal: Deal | None = None) -> pd.DataFrame:
    """Attachment/detachment points (subordination from the bottom of the
    stack up), rated bottom-to-top per market convention."""
    deal = deal or load_deal()
    rows = []
    attach = 0.0
    for name in reversed(TRANCHE_ORDER):  # equity first (bottom), AAA last (top)
        t = deal.tranche(name)
        detach = attach + t.size / deal.target_par * 100
        rows.append(dict(
            name=name, rating=t.rating, size=t.size, spread_bps=t.spread_bps,
            attachment_pct=attach, detachment_pct=detach, subordination_pct=attach,
        ))
        attach = detach
    df = pd.DataFrame(rows)
    return df.iloc[::-1].reset_index(drop=True)  # AAA first for display


def compute_wal_years(df_scenario: pd.DataFrame, tranche_name: str, quarters_per_year: float = 4.0) -> float:
    """Weighted-average life: quarter-weighted principal paydown, with any
    balance still outstanding at the end of the simulated horizon treated
    as a single balloon repayment in the final quarter (standard WAL
    convention when a run doesn't fully amortize a class within its
    modeled horizon)."""
    col = f"stop_principal_{tranche_name}_principal" if tranche_name != "equity" else "stop_principal_equity_residual_principal"
    principal = df_scenario.get(col, pd.Series(0.0, index=df_scenario.index)).fillna(0.0)
    quarters = df_scenario["period"].to_numpy()
    final_balance = df_scenario[f"balance_{tranche_name}"].iloc[-1]
    if final_balance > 1e-6:
        principal = principal.copy()
        principal.iloc[-1] += final_balance  # balloon at horizon end
    total = principal.sum()
    if total <= 0:
        return float("nan")
    return float((principal * quarters).sum() / total / quarters_per_year)


def build_wal_sensitivity_table(deal: Deal | None = None,
                                 scenario_keys: tuple[str, ...] = ("base", "covid_shock", "severe_recession",
                                                                    "post_reinvestment_amortization")) -> pd.DataFrame:
    deal = deal or load_deal()
    scenarios = build_scenarios(deal)
    rows = []
    for key in scenario_keys:
        df = run_scenario(deal, scenarios[key])
        for name in TRANCHE_ORDER:
            rows.append(dict(scenario=key, tranche=name, wal_years=compute_wal_years(df, name)))
    return pd.DataFrame(rows)


def main():
    deal = load_deal()
    cap_table = build_capital_structure_table(deal)
    print(cap_table.to_string(index=False))

    wal_table = build_wal_sensitivity_table(deal)
    print()
    print(wal_table.pivot(index="tranche", columns="scenario", values="wal_years")
          .reindex(TRANCHE_ORDER).to_string())

    out_dir = config.FINAL_DIR / "anatomy"
    write_parquet(cap_table, out_dir / "capital_structure.parquet", Provenance(
        source_urls=[deal.citation.get("source_url", "")], parser="src.anatomy.analysis_pricing.build_capital_structure_table",
        notes="Tranche sizes/spreads/ratings are circular figures (see config.ANATOMY_DEAL); attachment points are "
              "computed, not stated in the circular.",
    ))
    write_parquet(wal_table, out_dir / "wal_sensitivity.parquet", Provenance(
        source_urls=[deal.citation.get("source_url", "")], parser="src.anatomy.analysis_pricing.build_wal_sensitivity_table",
        notes="WAL is computed from this project's own simulated principal cash flows, not a circular or "
              "third-party figure.",
    ))
    print(f"\nwrote {out_dir / 'capital_structure.parquet'}")
    print(f"wrote {out_dir / 'wal_sensitivity.parquet'}")


if __name__ == "__main__":
    main()
