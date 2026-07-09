"""CUSIP-level tranche price panel from ETF holdings (Section 1).

Builds AAA price indices and cross-sectional dispersion from whichever funds/
dates scrape_holdings.py has reached (currently JAAA — an AAA-focused fund —
and JBBB). Time-series pieces (which deals cheapened most, tranche turnover)
need >=2 scrape dates and degrade gracefully to an empty, logged result
before that, exactly like analysis_flows.py / analysis_nav_dislocation.py.
"""
from __future__ import annotations

import logging
import re

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.etf.analysis_tranche_panel")

HOLDINGS_PATH = config.INTERIM_DIR / "etf_holdings.parquet"

OUT_INDEX = config.FINAL_DIR / "etf_aaa_price_index.parquet"
OUT_DISPERSION = config.FINAL_DIR / "etf_aaa_mark_dispersion.parquet"
OUT_MOVERS = config.FINAL_DIR / "etf_deal_movers.parquet"
OUT_TURNOVER = config.FINAL_DIR / "etf_tranche_turnover.parquet"

AAA_FUNDS = [t for t, m in config.CLO_ETF_TICKERS.items() if m["tranche_focus"] == "AAA"]

_CUSIP_PATTERN = re.compile(r"^[0-9A-Z]{9}$")
# CLO AAA tranches trade close to par; a "price" outside this band is a sign
# of a non-tranche line item (FX hedge notional, currency overlay) where par
# and market value aren't denominated the same way, not a real market price.
_SANE_PRICE_BAND = (80.0, 112.0)


def load_holdings() -> pd.DataFrame:
    if not HOLDINGS_PATH.exists():
        return pd.DataFrame()
    holdings = read_parquet(HOLDINGS_PATH).dropna(subset=["price"])
    valid_cusip = holdings["cusip"].fillna("").str.match(_CUSIP_PATTERN)
    in_band = holdings["price"].between(*_SANE_PRICE_BAND)
    dropped = (~(valid_cusip & in_band)).sum()
    if dropped:
        logger.warning("dropping %d/%d holdings rows as non-tranche line items or implausible marks "
                        "(bad CUSIP format or price outside %s)", dropped, len(holdings), _SANE_PRICE_BAND)
    return holdings[valid_cusip & in_band]


def aaa_price_index(holdings: pd.DataFrame) -> pd.DataFrame:
    """Equal-weight and par-weight AAA mark index per date, across AAA-focused funds."""
    aaa = holdings[holdings["fund"].isin(AAA_FUNDS)]
    if aaa.empty:
        logger.warning("no AAA-fund holdings cached yet (looked for %s)", AAA_FUNDS)
        return pd.DataFrame(columns=["date", "equal_weight_index", "par_weight_index", "n_positions"])

    def _agg(g):
        par_weight = (g["price"] * g["par"]).sum() / g["par"].sum() if g["par"].sum() else None
        return pd.Series({
            "equal_weight_index": g["price"].mean(),
            "par_weight_index": par_weight,
            "n_positions": len(g),
        })
    return aaa.groupby("date").apply(_agg, include_groups=False).reset_index()


def aaa_mark_dispersion(holdings: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional IQR of AAA marks per date — a stress thermometer."""
    aaa = holdings[holdings["fund"].isin(AAA_FUNDS)]
    if aaa.empty:
        return pd.DataFrame(columns=["date", "median_price", "iqr", "p10", "p90"])
    stats = aaa.groupby("date")["price"].agg(
        median_price="median",
        iqr=lambda s: s.quantile(0.75) - s.quantile(0.25),
        p10=lambda s: s.quantile(0.10),
        p90=lambda s: s.quantile(0.90),
    ).reset_index()
    return stats


def deal_movers(holdings: pd.DataFrame) -> pd.DataFrame:
    """Which deals/managers cheapened (or richened) most between the two most
    recent scrape dates. Needs >=2 dates per fund; empty otherwise."""
    if holdings.empty or holdings["date"].nunique() < 2:
        logger.warning("holdings history has <2 distinct dates; deal_movers needs at least two scrape_holdings.py runs")
        return pd.DataFrame(columns=["fund", "cusip", "manager_raw", "date_from", "date_to", "price_change"])

    rows = []
    for (fund, cusip), grp in holdings.groupby(["fund", "cusip"]):
        grp = grp.sort_values("date")
        if len(grp) < 2:
            continue
        first, last = grp.iloc[0], grp.iloc[-1]
        rows.append({
            "fund": fund, "cusip": cusip, "manager_raw": last["manager_raw"],
            "date_from": first["date"], "date_to": last["date"],
            "price_change": last["price"] - first["price"],
        })
    out = pd.DataFrame(rows)
    return out.sort_values("price_change").reset_index(drop=True) if len(out) else out


def tranche_turnover(holdings: pd.DataFrame) -> pd.DataFrame:
    """Entries/exits per fund between consecutive scrape dates."""
    if holdings.empty or holdings["date"].nunique() < 2:
        logger.warning("holdings history has <2 distinct dates; tranche_turnover needs at least two scrape_holdings.py runs")
        return pd.DataFrame(columns=["fund", "date_from", "date_to", "n_entries", "n_exits"])

    rows = []
    for fund, grp in holdings.groupby("fund"):
        dates = sorted(grp["date"].unique())
        for prev_date, curr_date in zip(dates[:-1], dates[1:]):
            prev_cusips = set(grp.loc[grp["date"] == prev_date, "cusip"])
            curr_cusips = set(grp.loc[grp["date"] == curr_date, "cusip"])
            rows.append({
                "fund": fund, "date_from": prev_date, "date_to": curr_date,
                "n_entries": len(curr_cusips - prev_cusips), "n_exits": len(prev_cusips - curr_cusips),
            })
    return pd.DataFrame(rows)


def run() -> dict[str, pd.DataFrame]:
    holdings = load_holdings()

    idx = aaa_price_index(holdings)
    write_parquet(idx, OUT_INDEX, Provenance(parser="src.etf.analysis_tranche_panel.aaa_price_index", source_urls=[]))

    disp = aaa_mark_dispersion(holdings)
    write_parquet(disp, OUT_DISPERSION, Provenance(parser="src.etf.analysis_tranche_panel.aaa_mark_dispersion", source_urls=[]))

    movers = deal_movers(holdings)
    write_parquet(movers, OUT_MOVERS, Provenance(parser="src.etf.analysis_tranche_panel.deal_movers", source_urls=[]))

    turnover = tranche_turnover(holdings)
    write_parquet(turnover, OUT_TURNOVER, Provenance(parser="src.etf.analysis_tranche_panel.tranche_turnover", source_urls=[]))

    logger.info("aaa_price_index=%d rows, dispersion=%d rows, movers=%d rows, turnover=%d rows",
                len(idx), len(disp), len(movers), len(turnover))
    return {"index": idx, "dispersion": disp, "movers": movers, "turnover": turnover}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
