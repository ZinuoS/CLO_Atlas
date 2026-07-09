"""CLO/credit manager landscape from Form ADV (Section 3): manager count
over time, RAUM concentration, entry/exit — the consolidation story. Real
multi-point history from config.ADV_BULK_SNAPSHOTS (2012/2018/2026), not a
single-day snapshot.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.edgar.analysis_managers")

ADV_PATH = config.INTERIM_DIR / "adv_firm_roster.parquet"

OUT_COUNTS = config.FINAL_DIR / "adv_manager_counts.parquet"
OUT_CONCENTRATION = config.FINAL_DIR / "adv_raum_concentration.parquet"
OUT_ENTRY_EXIT = config.FINAL_DIR / "adv_entry_exit.parquet"


def manager_counts_by_snapshot() -> pd.DataFrame:
    if not ADV_PATH.exists():
        logger.warning("no ADV data cached; run scrape_adv.py first")
        return pd.DataFrame(columns=["snapshot_date", "n_firms", "total_raum_usd"])
    adv = read_parquet(ADV_PATH)
    g = adv.groupby("snapshot_date").agg(
        n_firms=("firm_name", "nunique"),
        total_raum_usd=("raum_total_usd", "sum"),
    ).reset_index()
    return g.sort_values("snapshot_date")


def raum_concentration_by_snapshot() -> pd.DataFrame:
    if not ADV_PATH.exists():
        return pd.DataFrame(columns=["snapshot_date", "hhi", "top10_share"])
    adv = read_parquet(ADV_PATH).dropna(subset=["raum_total_usd"])
    adv = adv[adv["raum_total_usd"] > 0]
    rows = []
    for date, grp in adv.groupby("snapshot_date"):
        total = grp["raum_total_usd"].sum()
        shares = grp["raum_total_usd"] / total
        hhi = (shares ** 2).sum() * 10_000
        top10_share = shares.sort_values(ascending=False).head(10).sum()
        rows.append({"snapshot_date": date, "hhi": hhi, "top10_share": top10_share, "n_firms": len(grp)})
    return pd.DataFrame(rows).sort_values("snapshot_date")


def entry_exit() -> pd.DataFrame:
    """Firms present in the earliest snapshot but not the latest (exits) and
    vice versa (entries) — the consolidation story, using firm_name as the
    join key (CRD# would be cleaner but isn't populated consistently across
    the 2012 vintage export)."""
    if not ADV_PATH.exists():
        return pd.DataFrame(columns=["firm_name", "status"])
    adv = read_parquet(ADV_PATH)
    dates = sorted(adv["snapshot_date"].unique())
    if len(dates) < 2:
        logger.warning("only %d ADV snapshot(s); entry_exit needs >=2", len(dates))
        return pd.DataFrame(columns=["firm_name", "status"])
    first, last = dates[0], dates[-1]
    first_names = set(adv.loc[adv["snapshot_date"] == first, "firm_name"].str.upper().str.strip())
    last_names = set(adv.loc[adv["snapshot_date"] == last, "firm_name"].str.upper().str.strip())
    exits = pd.DataFrame({"firm_name": sorted(first_names - last_names), "status": "exited"})
    entries = pd.DataFrame({"firm_name": sorted(last_names - first_names), "status": "entered"})
    out = pd.concat([exits, entries], ignore_index=True)
    out.attrs["window"] = f"{first} to {last}"
    return out


def run() -> dict[str, pd.DataFrame]:
    counts = manager_counts_by_snapshot()
    write_parquet(counts, OUT_COUNTS, Provenance(parser="src.edgar.analysis_managers.manager_counts_by_snapshot", source_urls=[]))

    concentration = raum_concentration_by_snapshot()
    write_parquet(concentration, OUT_CONCENTRATION, Provenance(parser="src.edgar.analysis_managers.raum_concentration_by_snapshot", source_urls=[]))

    churn = entry_exit()
    write_parquet(churn, OUT_ENTRY_EXIT, Provenance(parser="src.edgar.analysis_managers.entry_exit", source_urls=[]))

    logger.info("manager_counts=%d snapshots, concentration=%d snapshots, entry_exit=%d firms",
                len(counts), len(concentration), len(churn))
    return {"counts": counts, "concentration": concentration, "entry_exit": churn}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
