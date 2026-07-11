"""Bank credit tightening (SLOOS) vs. lending stock, spreads, and CLO
issuance (slide 2 supporting material / appendix).

CLO issuance is NOT overlaid here: data/final/clo_issuance_cycle.parquet
(Section 4) is an empty frame — SIFMA, the only issuance-volume source found,
is gated (docs/excluded_sources.md) — so src.official.analysis_issuance never
had real rows to begin with. That gap is reported, not silently dropped or
faked; see `issuance_overlay_status()` below.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.macro.analysis_tightening")

FRED_PATH = config.INTERIM_DIR / "macro_fred_series.parquet"
ISSUANCE_PATH = config.FINAL_DIR / "clo_issuance_cycle.parquet"

OUT_SLOOS_HISTORY = config.FINAL_DIR / "macro_sloos_history.parquet"
OUT_SLOOS_VS_LENDING = config.FINAL_DIR / "macro_sloos_vs_lending_xcorr.parquet"
OUT_SLOOS_VS_SPREADS = config.FINAL_DIR / "macro_sloos_vs_spreads.parquet"


def _load_fred() -> pd.DataFrame:
    df = read_parquet(FRED_PATH)
    df["date"] = pd.to_datetime(df["date"])
    return df


def sloos_history() -> pd.DataFrame:
    """SLOOS net-tightening history (large/medium firms) with each quarter's
    percentile within its own full history — "how unusual is now."""
    fred = _load_fred()
    sloos = fred[fred["series"] == "SLOOS_TIGHTENING_LARGE"].sort_values("date").dropna(subset=["value"])
    if sloos.empty:
        logger.warning("no SLOOS series cached; sloos_history is empty")
        return pd.DataFrame(columns=["date", "net_pct_tightening", "percentile"])
    out = sloos[["date", "value"]].rename(columns={"value": "net_pct_tightening"}).reset_index(drop=True)
    out["percentile"] = out["net_pct_tightening"].rank(pct=True)
    return out


def sloos_vs_lending_xcorr(max_lead_quarters: int = 4) -> pd.DataFrame:
    """Descriptive cross-correlation of SLOOS net tightening (quarterly)
    against BUSLOANS y/y growth, SLOOS led 0-4 quarters. No causal claim —
    correlation only, reported at every lag so the honest lag (if any) shows
    rather than being cherry-picked."""
    fred = _load_fred()
    sloos = fred[fred["series"] == "SLOOS_TIGHTENING_LARGE"].sort_values("date").dropna(subset=["value"])
    busloans = fred[fred["series"] == "BUSLOANS"].sort_values("date").dropna(subset=["value"])
    if sloos.empty or busloans.empty:
        logger.warning("missing SLOOS or BUSLOANS; sloos_vs_lending_xcorr is empty")
        return pd.DataFrame(columns=["lead_quarters", "correlation", "n_obs"])

    sloos_q = sloos.set_index("date")["value"].resample("QS").mean()
    busloans_q = busloans.set_index("date")["value"].resample("QS").last()
    busloans_yoy = busloans_q.pct_change(4)

    rows = []
    for lag in range(0, max_lead_quarters + 1):
        shifted_sloos = sloos_q.shift(lag)  # SLOOS led by `lag` quarters -> shift forward to align with later BUSLOANS
        aligned = pd.concat([shifted_sloos.rename("sloos"), busloans_yoy.rename("busloans_yoy")], axis=1).dropna()
        if len(aligned) < 8:
            continue
        corr = aligned["sloos"].corr(aligned["busloans_yoy"])
        rows.append({"lead_quarters": lag, "correlation": corr, "n_obs": len(aligned)})
    return pd.DataFrame(rows)


def sloos_vs_spreads() -> pd.DataFrame:
    """SLOOS net tightening vs. HY OAS, quarterly, decade-tagged for the
    scatter's color encoding."""
    fred = _load_fred()
    sloos = fred[fred["series"] == "SLOOS_TIGHTENING_LARGE"].sort_values("date").dropna(subset=["value"])
    hy_oas = fred[fred["series"] == "HY_OAS"].sort_values("date").dropna(subset=["value"])
    if sloos.empty or hy_oas.empty:
        logger.warning("missing SLOOS or HY_OAS; sloos_vs_spreads is empty")
        return pd.DataFrame(columns=["date", "net_pct_tightening", "hy_oas", "decade"])

    sloos_q = sloos.set_index("date")["value"].resample("QS").mean()
    hy_oas_q = hy_oas.set_index("date")["value"].resample("QS").mean()
    merged = pd.concat([sloos_q.rename("net_pct_tightening"), hy_oas_q.rename("hy_oas")], axis=1).dropna().reset_index()
    merged = merged.rename(columns={"index": "date"})
    merged["decade"] = (merged["date"].dt.year // 10) * 10
    return merged


def issuance_overlay_status() -> dict:
    """Whether a real SLOOS-vs-CLO-issuance overlay could be built. Reported
    explicitly rather than silently skipped — see module docstring."""
    if not ISSUANCE_PATH.exists():
        return {"available": False, "reason": "clo_issuance_cycle.parquet not found; run src.official.analysis_issuance first"}
    issuance = read_parquet(ISSUANCE_PATH)
    if issuance.empty:
        return {"available": False,
                "reason": "clo_issuance_cycle.parquet is empty: SIFMA (the only issuance-volume source found) is gated "
                          "(see docs/excluded_sources.md), so Section 4 never populated it. "
                          "No CLO-issuance overlay is possible from free data at this time."}
    return {"available": True, "reason": "", "n_rows": len(issuance)}


def run() -> dict[str, pd.DataFrame]:
    history = sloos_history()
    write_parquet(history, OUT_SLOOS_HISTORY, Provenance(parser="src.macro.analysis_tightening.sloos_history", source_urls=[]))

    xcorr = sloos_vs_lending_xcorr()
    write_parquet(xcorr, OUT_SLOOS_VS_LENDING, Provenance(
        parser="src.macro.analysis_tightening.sloos_vs_lending_xcorr", source_urls=[],
        notes="Descriptive cross-correlation only; no causal claim.",
    ))

    spreads = sloos_vs_spreads()
    write_parquet(spreads, OUT_SLOOS_VS_SPREADS, Provenance(parser="src.macro.analysis_tightening.sloos_vs_spreads", source_urls=[]))

    status = issuance_overlay_status()
    logger.info("sloos_history=%d quarters, xcorr_lags=%d, spreads=%d quarters, issuance_overlay_available=%s (%s)",
                len(history), len(xcorr), len(spreads), status["available"], status["reason"])
    return {"sloos_history": history, "xcorr": xcorr, "spreads": spreads, "issuance_overlay_status": status}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
