"""CLO trading liquidity from TRACE-sourced pricing tables (Section 4).

Today's cross-section by rating band/vintage is real; the weekly-volume-with-
event-flags time series and the volume-vs-ETF-discount dual panel both need
history that accretes from repeated daily runs (see analysis_liquidity.py).
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import numpy as np

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, WARM_GRAY, apply_theme, save_figure

logger = logging.getLogger("clo_atlas.official.viz_liquidity")

VOLUME_PATH = config.FINAL_DIR / "trace_volume_by_band.parquet"
SPLIT_PATH = config.FINAL_DIR / "trace_dealer_customer_split.parquet"


def viz_volume_by_band():
    apply_theme()
    vol = read_parquet(VOLUME_PATH)
    if vol.empty:
        logger.warning("no TRACE volume data cached; skipping viz_volume_by_band")
        return None
    latest_date = vol["date"].max()
    snap = vol[vol["date"] == latest_date]
    bands = ["AAA", "NON-AAA IG", "NON-INVESTMENT GRADE"]
    pre = snap[snap["vintage"] == "PRE-2023"].set_index("rating_band").reindex(bands)["volume_usd_000s"] / 1000
    post = snap[snap["vintage"] == "2023-2026"].set_index("rating_band").reindex(bands)["volume_usd_000s"] / 1000

    x = np.arange(len(bands))
    width = 0.35
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(x - width / 2, pre.values, width, label="Pre-2023 vintage", color=WARM_GRAY[1])
    ax.bar(x + width / 2, post.values, width, label="2023-2026 vintage", color=ACCENT)
    ax.set_xticks(x)
    ax.set_xticklabels(["AAA", "Non-AAA IG", "Non-investment grade"])
    ax.set_ylabel("TRACE-reported volume that day ($ millions)")
    ax.legend(loc="upper right")

    png, svg = save_figure(
        fig, "viz_trace_volume_by_band",
        headline="AAA CLOs trade more than the rest of the stack combined.",
        subtitle=f"TRACE-reported CLO trading volume by rating band and vintage, {latest_date}. "
                  "A weekly time series with event flags accretes as this project runs daily.",
        source="clo-atlas, from FINRA/ICE Data Services structured-product pricing tables",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def viz_dealer_customer_split():
    apply_theme()
    split = read_parquet(SPLIT_PATH)
    if split.empty:
        logger.warning("no TRACE dealer/customer split cached; skipping viz_dealer_customer_split")
        return None
    latest_date = split["date"].max()
    snap = split[(split["date"] == latest_date) & (split["vintage"] == "PRE-2023")]
    bands = ["AAA", "NON-AAA IG", "NON-INVESTMENT GRADE"]
    pivot = snap.pivot(index="rating_band", columns="side", values="volume_usd_000s").reindex(bands) / 1000

    fig, ax = plt.subplots(figsize=(8, 5))
    bottom = np.zeros(len(bands))
    colors = {"CUSTOMER BUY": ACCENT, "CUSTOMER SELL": WARM_GRAY[1], "DEALER TO DEALER": WARM_GRAY[2]}
    for side in ["CUSTOMER BUY", "CUSTOMER SELL", "DEALER TO DEALER"]:
        vals = pivot[side].fillna(0).values if side in pivot.columns else np.zeros(len(bands))
        ax.bar(["AAA", "Non-AAA IG", "Non-investment grade"], vals, bottom=bottom, label=side.title(), color=colors[side])
        bottom += vals
    ax.set_ylabel("Volume ($ millions)")
    ax.legend(loc="upper right")

    png, svg = save_figure(
        fig, "viz_dealer_customer_split",
        headline="Customer-to-dealer trades dominate CLO flow; dealers rarely trade with each other.",
        subtitle=f"TRACE-reported volume by counterparty side, pre-2023 vintage tranches, {latest_date}.",
        source="clo-atlas, from FINRA/ICE Data Services structured-product pricing tables",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_volume_by_band()
    viz_dealer_customer_split()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
