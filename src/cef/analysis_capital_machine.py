"""The centerpiece: the premium-funded ATM flywheel (Section 2 deep-dive,
Oxford Lane at the center).

The mechanism, each link measured from real disclosures, not asserted:
  1. Two independent, real NAV disclosure channels are merged into one
     series: OXLC's 424B3 "FINANCIAL UPDATE" paragraphs (`scrape_capital_
     actions.scrape_nav_disclosures`, tied to ATM registration activity so
     it goes quiet whenever issuance does) and OXLC's own monthly/quarterly
     NAV-update press releases (`scrape_nav_press_releases`, discovered
     2026-07-15 -- a GlobeNewswire-distributed channel independent of ATM
     activity, so it stays current even through the mid-2025 issuance
     lull). Both are joined against OXLC's own daily market price (Section
     2's `cef_prices.parquet`) to compute a REAL historical premium/
     discount at each disclosure date. This is richer than Section 2's own
     premium/discount table, which is limited to a single current-day
     book-value snapshot (yfinance has no historical NAV for these
     equity-classified tickers) — see that module's docstring.
  2. The same 424B3 filings' "prior sales" paragraphs give a real ATM
     issuance tape (`cef_atm_tape.parquet`): cumulative shares sold and
     gross/net proceeds since each registration statement's start date.
  3. This module derives INCREMENTAL (not cumulative) shares/proceeds per
     filing interval, aligns each interval's END with the nearest NAV
     disclosure to get that period's approximate prevailing premium, and
     reports the premium-vs-issuance relationship as a plain correlation
     with its own publication date — not a fitted causal model.

When the fund trades at a premium, ATM issuance is NAV-accretive (existing
shareholders benefit, per-share NAV rises) and raises cash that must be
deployed into CLO equity — that is the flywheel. Whether the data actually
shows issuance concentrated in premium periods is reported, not assumed.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.cef.analysis_capital_machine")

ATM_TAPE_PATH = config.INTERIM_DIR / "cef_atm_tape.parquet"
NAV_DISCLOSURES_PATH = config.INTERIM_DIR / "cef_nav_disclosures.parquet"
NAV_PRESS_RELEASES_PATH = config.INTERIM_DIR / "cef_oxlc_nav_press_releases.parquet"
PRICES_PATH = config.INTERIM_DIR / "cef_prices.parquet"
SPLITS_PATH = config.INTERIM_DIR / "cef_stock_splits.parquet"
CLO_POSITIONS_PATH = config.INTERIM_DIR / "cef_clo_positions.parquet"
BOOKVALUE_SNAPSHOT_PATH = config.INTERIM_DIR / "cef_bookvalue_snapshots.parquet"

OUT_PREMIUM_HISTORY = config.FINAL_DIR / "capital_machine_premium_history.parquet"
OUT_INCREMENTAL_ISSUANCE = config.FINAL_DIR / "capital_machine_incremental_issuance.parquet"
OUT_ANNUAL_BUYING_POWER = config.FINAL_DIR / "capital_machine_annual_buying_power.parquet"
OUT_LATEST_NAV_ESTIMATE = config.FINAL_DIR / "capital_machine_latest_nav_estimate.parquet"

FUND = "OXLC"  # the only fund with both a real ATM tape and real NAV disclosures


def _cumulative_split_factor(ticker: str, as_of: pd.Timestamp) -> float:
    """Product of all split ratios effective AFTER `as_of` for this ticker.
    Yahoo's historical "Close" is retroactively adjusted for splits (not
    just dividends — confirmed by comparing yfinance's Close series across
    OXLC's 2025-09-08 1-for-5 reverse split date, which shows no
    discontinuity, i.e. the whole series is already rebased), so an NAV
    figure disclosed BEFORE a later split must be divided by that split's
    ratio to land on the same post-split-equivalent per-share basis as the
    (already-adjusted) price series it's being compared against."""
    if not SPLITS_PATH.exists():
        return 1.0
    splits = read_parquet(SPLITS_PATH)
    splits = splits[(splits["ticker"] == ticker) & (pd.to_datetime(splits["split_date"]) > as_of)]
    factor = 1.0
    for ratio in splits["ratio"]:
        factor *= ratio
    return factor


def _load_nav_disclosures(fund: str) -> pd.DataFrame:
    """424B3 ATM-supplement 'financial update' paragraphs -- real, but goes
    quiet whenever ATM issuance does (see module docstring). `reference_date`
    (the filing date) is what split-adjustment should key off of, not the
    as-of date -- see `premium_history`'s docstring on why."""
    if not NAV_DISCLOSURES_PATH.exists():
        return pd.DataFrame(columns=["date", "reference_date", "nav_mid", "shares_outstanding", "nav_source"])
    nav = read_parquet(NAV_DISCLOSURES_PATH)
    nav = nav[nav["ticker"] == fund].dropna(subset=["nav_mid"]).copy()
    if nav.empty:
        return pd.DataFrame(columns=["date", "reference_date", "nav_mid", "shares_outstanding", "nav_source"])
    nav["date"] = pd.to_datetime(nav["nav_as_of"])
    nav["reference_date"] = pd.to_datetime(nav["filing_date"])
    nav["nav_source"] = "424B3 ATM supplement"
    return nav[["date", "reference_date", "nav_mid", "shares_outstanding", "nav_source"]]


def _load_nav_press_releases(fund: str) -> pd.DataFrame:
    """OXLC's own monthly/quarterly NAV-update press releases (GlobeNewswire)
    -- real, independent of ATM activity, current through mid-2026 (see
    scrape_nav_press_releases.py). Only meaningful for OXLC; other funds
    don't have this scraper built. `reference_date` (the release date) is
    what split-adjustment should key off of: a release published AFTER the
    2025-09-08 reverse split restates even its own PRIOR-period comparison
    figures ("compared with a NAV per share on <date> of $X") on the
    current, post-split share basis -- confirmed by checking the actual
    trajectory of values across the split date for a discontinuity, and
    finding none, once keyed on reference_date instead of the as-of date."""
    if fund != "OXLC" or not NAV_PRESS_RELEASES_PATH.exists():
        return pd.DataFrame(columns=["date", "reference_date", "nav_mid", "shares_outstanding", "nav_source"])
    pr = read_parquet(NAV_PRESS_RELEASES_PATH)
    if pr.empty:
        return pd.DataFrame(columns=["date", "reference_date", "nav_mid", "shares_outstanding", "nav_source"])
    pr = pr.rename(columns={"as_of_date": "date"}).copy()
    pr["date"] = pd.to_datetime(pr["date"])
    pr["reference_date"] = pd.to_datetime(pr["release_date"])
    pr["nav_source"] = pr["figure_type"].map({
        "monthly_estimate": "OXLC press release (monthly estimate)",
        "quarterly_actual": "OXLC press release (quarterly actual)",
    }).fillna("OXLC press release")
    return pr[["date", "reference_date", "nav_mid", "shares_outstanding", "nav_source"]]


def premium_history(fund: str = FUND) -> pd.DataFrame:
    """Real historical premium/discount at each disclosed NAV date, merging
    two independent real disclosure channels (see module docstring) —
    market close price (not dividend-adjusted, but IS split-adjusted by
    Yahoo regardless — see `_cumulative_split_factor`) vs. the disclosed
    NAV midpoint, rescaled onto the same post-split basis, nearest trading
    day. Where both channels disclose the same date, the press release
    figure wins (it's OXLC's more complete, investor-facing number)."""
    if not PRICES_PATH.exists():
        logger.warning("missing price history; premium_history is empty")
        return pd.DataFrame(columns=["date", "nav_mid", "market_price", "premium_discount"])

    atm_nav = _load_nav_disclosures(fund)
    pr_nav = _load_nav_press_releases(fund)
    nav = pd.concat([df for df in (atm_nav, pr_nav) if not df.empty], ignore_index=True) \
        if not (atm_nav.empty and pr_nav.empty) else atm_nav
    if nav.empty:
        logger.warning("no NAV disclosures from either channel; premium_history is empty")
        return pd.DataFrame(columns=["date", "nav_mid", "market_price", "premium_discount"])
    # Press-release figures win on an exact-date collision (see docstring).
    nav["_source_rank"] = nav["nav_source"].str.startswith("OXLC press release").astype(int)
    nav = nav.sort_values("_source_rank").drop_duplicates(subset="date", keep="last").drop(columns="_source_rank")

    # Rescale each disclosure onto today's share basis: dividing by the
    # split factor accounts for a later reverse split (fewer, pricier
    # shares) the same way Yahoo's price series already has been. Keyed on
    # reference_date (when the figure was actually published), not the
    # as-of date -- a figure published after the split already expresses
    # even a pre-split as-of date on the current share basis.
    split_factor = nav["reference_date"].apply(lambda d: _cumulative_split_factor(fund, d))
    nav["nav_mid_adj"] = nav["nav_mid"] / split_factor
    nav["shares_outstanding_adj"] = nav["shares_outstanding"] * split_factor

    prices = read_parquet(PRICES_PATH)
    prices = prices[prices["ticker"] == fund].sort_values("date").copy()
    prices["date"] = pd.to_datetime(prices["date"])

    merged = pd.merge_asof(nav.sort_values("date"), prices[["date", "close"]].sort_values("date"),
                            on="date", direction="nearest", tolerance=pd.Timedelta(days=10))
    merged = merged.dropna(subset=["close"]).rename(columns={"close": "market_price"})
    merged["premium_discount"] = merged["market_price"] / merged["nav_mid_adj"] - 1
    return merged[["date", "nav_mid_adj", "market_price", "premium_discount", "shares_outstanding_adj", "nav_source"]] \
        .rename(columns={"nav_mid_adj": "nav_mid", "shares_outstanding_adj": "shares_outstanding"}).sort_values("date")


def latest_nav_estimate(fund: str = FUND) -> dict | None:
    """A fresher NAV-per-share estimate than `premium_history()` can offer,
    for the gap after OXLC's most recent 424B3 "financial update" disclosure.

    OXLC only discloses NAV-per-share in the "FINANCIAL UPDATE" paragraph of
    an ATM 424B3/497 supplement (see scrape_nav_disclosures's docstring) --
    when the fund slows or pauses ATM issuance, that trail goes stale even
    though the fund keeps filing NPORT-P (portfolio holdings, quarterly,
    required of every registered fund regardless of ATM activity) and its
    share count keeps moving on the open market.

    NPORT-P's <netAssets> total (fund-level, parsed onto every row by
    src.common.nport.parse_nport_xml) divided by the fund's current
    yfinance-reported share count approximates NAV/share as of the NPORT-P
    filing's report period -- not an official per-share figure the fund
    itself published, so this is TO-VERIFY methodology, kept separate from
    the disclosure-based series in `premium_history()` rather than merged
    into it silently."""
    if not CLO_POSITIONS_PATH.exists() or not BOOKVALUE_SNAPSHOT_PATH.exists() or not PRICES_PATH.exists():
        return None
    positions = read_parquet(CLO_POSITIONS_PATH)
    positions = positions[(positions["fund"] == fund) & positions["net_assets"].notna()]
    if positions.empty:
        return None
    latest = positions.sort_values("period").iloc[-1]
    period_date = pd.Timestamp(latest["period"])
    net_assets = float(latest["net_assets"])

    snapshot = read_parquet(BOOKVALUE_SNAPSHOT_PATH)
    snapshot = snapshot[snapshot["ticker"] == fund].dropna(subset=["shares_outstanding"])
    if snapshot.empty:
        return None
    shares_outstanding = float(snapshot.sort_values("date").iloc[-1]["shares_outstanding"])
    nav_per_share = net_assets / shares_outstanding

    prices = read_parquet(PRICES_PATH)
    prices = prices[prices["ticker"] == fund].copy()
    prices["date"] = pd.to_datetime(prices["date"])
    prices["gap"] = (prices["date"] - period_date).abs()
    if prices.empty:
        return None
    nearest = prices.sort_values("gap").iloc[0]
    market_price = float(nearest["close"])

    return {
        "fund": fund, "period": period_date, "net_assets": net_assets,
        "shares_outstanding": shares_outstanding, "nav_per_share": nav_per_share,
        "market_price_date": nearest["date"], "market_price": market_price,
        "premium_discount": market_price / nav_per_share - 1,
    }


def incremental_issuance(fund: str = FUND) -> pd.DataFrame:
    """Cumulative-since-era-start ATM figures -> incremental shares/proceeds
    per filing interval. A new "era" starts whenever period_start changes
    (a new registration statement); the era's first filing is itself the
    first interval (nothing to diff against)."""
    if not ATM_TAPE_PATH.exists():
        return pd.DataFrame(columns=["filing_date", "period_start", "incremental_shares", "incremental_net_proceeds_millions"])
    tape = read_parquet(ATM_TAPE_PATH)
    tape = tape[tape["ticker"] == fund].copy()
    if tape.empty:
        return pd.DataFrame(columns=["filing_date", "period_start", "incremental_shares", "incremental_net_proceeds_millions"])
    tape["filing_date"] = pd.to_datetime(tape["filing_date"])
    tape = tape.sort_values("filing_date")

    rows = []
    for era, grp in tape.groupby("period_start", sort=False):
        grp = grp.sort_values("filing_date")
        prev_shares, prev_net = 0, 0.0
        for _, r in grp.iterrows():
            rows.append({
                "filing_date": r["filing_date"], "period_start": era, "period_end": r["period_end"],
                "incremental_shares": r["shares_sold"] - prev_shares,
                "incremental_net_proceeds_millions": r["net_proceeds_millions"] - prev_net,
            })
            prev_shares, prev_net = r["shares_sold"], r["net_proceeds_millions"]
    return pd.DataFrame(rows).sort_values("filing_date")


def premium_vs_issuance(premium: pd.DataFrame, issuance: pd.DataFrame) -> pd.DataFrame:
    """Each issuance interval matched to the nearest premium/discount
    disclosure — the flywheel's two halves on one row, with the
    correlation reported at call time, not baked into the table."""
    if premium.empty or issuance.empty:
        return pd.DataFrame(columns=["filing_date", "premium_discount", "incremental_net_proceeds_millions"])
    merged = pd.merge_asof(
        issuance.sort_values("filing_date"), premium[["date", "premium_discount"]].sort_values("date"),
        left_on="filing_date", right_on="date", direction="nearest", tolerance=pd.Timedelta(days=45),
    )
    return merged.dropna(subset=["premium_discount"])


def annual_buying_power(issuance: pd.DataFrame) -> pd.DataFrame:
    """Net proceeds raised per year — this project's estimate of CLO-equity
    buying power created annually by the ATM program (not all proceeds are
    necessarily deployed into CLO equity same-year, but that is the fund's
    stated investment objective)."""
    if issuance.empty:
        return pd.DataFrame(columns=["year", "net_proceeds_millions", "shares_issued"])
    df = issuance.copy()
    df["year"] = pd.to_datetime(df["filing_date"]).dt.year
    return df.groupby("year").agg(
        net_proceeds_millions=("incremental_net_proceeds_millions", "sum"),
        shares_issued=("incremental_shares", "sum"),
    ).reset_index()


def run() -> dict[str, pd.DataFrame]:
    premium = premium_history()
    write_parquet(premium, OUT_PREMIUM_HISTORY, Provenance(
        parser="src.cef.analysis_capital_machine.premium_history", source_urls=[],
        notes="Real historical premium/discount from OXLC's own disclosed NAV estimates + market close price, "
              "not the single current-day book-value snapshot Section 2's own table is limited to.",
    ))

    issuance = incremental_issuance()
    write_parquet(issuance, OUT_INCREMENTAL_ISSUANCE, Provenance(
        parser="src.cef.analysis_capital_machine.incremental_issuance", source_urls=[]))

    matched = premium_vs_issuance(premium, issuance)
    corr = matched[["premium_discount", "incremental_net_proceeds_millions"]].corr().iloc[0, 1] if len(matched) > 2 else None

    buying_power = annual_buying_power(issuance)
    write_parquet(buying_power, OUT_ANNUAL_BUYING_POWER, Provenance(
        parser="src.cef.analysis_capital_machine.annual_buying_power", source_urls=[],
        notes="Sum of incremental net ATM proceeds per year — this project's buying-power estimate, "
              "not a claim that 100% of proceeds are deployed into CLO equity the same year.",
    ))

    nav_estimate = latest_nav_estimate()
    if nav_estimate is not None:
        write_parquet(pd.DataFrame([nav_estimate]), OUT_LATEST_NAV_ESTIMATE, Provenance(
            parser="src.cef.analysis_capital_machine.latest_nav_estimate", source_urls=[],
            notes="TO-VERIFY methodology: NPORT-P <netAssets> (fund-level total, official/SEC-filed) divided by "
                  "yfinance's current shares-outstanding count -- an approximation, not an official per-share NAV "
                  "figure OXLC itself published, kept separate from the disclosure-based premium_history series.",
        ))
        logger.info("latest_nav_estimate: %s premium/discount as of NPORT-P period %s (vs. disclosure-based "
                     "series ending %s)", f"{nav_estimate['premium_discount']:+.1%}", nav_estimate["period"].date(),
                     premium["date"].max().date() if len(premium) else "n/a")

    logger.info("premium_history=%d disclosures, incremental_issuance=%d intervals, "
                "premium-vs-issuance correlation=%s, annual_buying_power=%d years",
                len(premium), len(issuance), f"{corr:.2f}" if corr is not None else "n/a", len(buying_power))
    return {"premium_history": premium, "incremental_issuance": issuance,
            "premium_vs_issuance": matched, "annual_buying_power": buying_power,
            "latest_nav_estimate": nav_estimate}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
