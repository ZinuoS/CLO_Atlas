"""The signature exhibit (Section 2 deep-dive, Oxford Lane centerpiece):
premium/discount, quarterly net shares issued, and cumulative capital
raised — three aligned panels, one time axis, telling the flywheel story
exactly as the data shows it (see analysis_capital_machine.py's docstring:
the simple premium-vs-issuance correlation is weak and slightly negative —
issuance scale has grown secularly over time more than it has tracked the
size of the premium period to period).

The premium/discount series merges two real, independent OXLC disclosure
channels (424B3 ATM supplements + OXLC's own NAV-update press releases,
discovered 2026-07-15) — see analysis_capital_machine.premium_history's
docstring. The press-release channel is what makes this current: it isn't
tied to ATM activity, so it kept disclosing through the second half of
2025 and into 2026 even as the 424B3 channel went quiet.
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import pandas as pd

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, INK, INK_MUTED, WARM_GRAY, apply_theme, format_date_axis, save_figure

logger = logging.getLogger("clo_atlas.cef.viz_flywheel")

PREMIUM_PATH = config.FINAL_DIR / "capital_machine_premium_history.parquet"
ISSUANCE_PATH = config.FINAL_DIR / "capital_machine_incremental_issuance.parquet"
BUYING_POWER_PATH = config.FINAL_DIR / "capital_machine_annual_buying_power.parquet"


def viz_flywheel():
    apply_theme()
    premium = read_parquet(PREMIUM_PATH)
    issuance = read_parquet(ISSUANCE_PATH)
    if premium.empty or issuance.empty:
        logger.warning("no premium/issuance data; skipping viz_flywheel")
        return None
    premium = premium.copy().sort_values("date")
    premium["date"] = pd.to_datetime(premium["date"])
    issuance = issuance.copy()
    issuance["filing_date"] = pd.to_datetime(issuance["filing_date"])
    issuance["cumulative_net_proceeds_millions"] = issuance["incremental_net_proceeds_millions"].cumsum()

    date_min = min(premium["date"].min(), issuance["filing_date"].min())
    date_max = max(premium["date"].max(), issuance["filing_date"].max())

    # How long has the discount held, as of the freshest real disclosure --
    # computed from the data, not asserted, so the headline can't drift out
    # of sync with what's actually plotted.
    trailing_negative = 0
    for v in premium["premium_discount"].iloc[::-1]:
        if v < 0:
            trailing_negative += 1
        else:
            break
    currently_discount = trailing_negative > 0
    discount_since = premium["date"].iloc[-trailing_negative] if trailing_negative else None

    fig, axes = plt.subplots(3, 1, figsize=(9.5, 9), sharex=True, gridspec_kw={"height_ratios": [1, 1, 1.1]})
    ax_premium, ax_issuance, ax_cumulative = axes

    for source, color in [("424B3 ATM supplement", WARM_GRAY[1]), (None, ACCENT)]:
        mask = (premium["nav_source"] == source) if source else premium["nav_source"].str.startswith("OXLC press release")
        label = source if source else "OXLC NAV press release (monthly + quarterly)"
        ax_premium.scatter(premium.loc[mask, "date"], premium.loc[mask, "premium_discount"] * 100,
                            color=color, s=22, zorder=4, label=label)
    ax_premium.plot(premium["date"], premium["premium_discount"] * 100, color=INK_MUTED, linewidth=1.0, zorder=3, alpha=0.6)
    ax_premium.axhline(0, color=INK_MUTED, linewidth=0.8)

    if currently_discount:
        months = max(1, round((premium["date"].iloc[-1] - discount_since).days / 30))
        title = f"Every month-end has shown a discount since {discount_since.strftime('%B %Y')} ({months} months and counting)"
    else:
        title = "Oxford Lane has traded at a premium to disclosed NAV at every observed month-end"
    ax_premium.set_ylabel("Premium/(discount) to NAV (%)")
    ax_premium.set_title(title, loc="left", fontsize=10)
    ax_premium.legend(loc="upper left", fontsize=7.5, frameon=False)

    ax_issuance.bar(issuance["filing_date"], issuance["incremental_net_proceeds_millions"], color=WARM_GRAY[1], width=25)
    ax_issuance.set_ylabel("Net ATM proceeds\nper interval ($M)")
    ax_issuance.set_title("...while ATM issuance has scaled up roughly ten-fold since 2020", loc="left", fontsize=10)

    ax_cumulative.fill_between(issuance["filing_date"], issuance["cumulative_net_proceeds_millions"], color=ACCENT, alpha=0.25)
    ax_cumulative.plot(issuance["filing_date"], issuance["cumulative_net_proceeds_millions"], color=ACCENT, linewidth=1.8)
    ax_cumulative.set_ylabel("Cumulative net ATM\nproceeds raised ($M)")
    total = issuance["incremental_net_proceeds_millions"].sum()
    ax_cumulative.annotate(f"${total:,.0f}M raised since 2016", xy=(issuance["filing_date"].iloc[-1], issuance["cumulative_net_proceeds_millions"].iloc[-1]),
                            xytext=(-160, -20), textcoords="offset points", fontsize=9.5, color=INK, fontweight="bold")
    ax_cumulative.annotate("ATM tape ends here --\nno 424B3 filed since", xy=(issuance["filing_date"].iloc[-1], issuance["cumulative_net_proceeds_millions"].iloc[-1]),
                            xytext=(8, 8), textcoords="offset points", fontsize=7, color=INK_MUTED)

    for ax in axes:
        ax.set_xlim(date_min, date_max)
    format_date_axis(ax_cumulative, interval_months=12)

    if currently_discount:
        headline = (f"Oxford Lane's ATM program raised over a billion dollars at a premium -- now a "
                     f"{abs(premium['premium_discount'].iloc[-1]):.0%} discount, {months} months running.")
        notes = ("New ATM issuance at a discount is NAV-dilutive to existing holders, the opposite of the "
                 "premium-funded mechanic the rest of this chart documents -- while the discount holds, the "
                 "flywheel this section describes should mechanically be paused, and the ATM tape (middle/bottom "
                 "panels) not extending past 2025 is consistent with that: no incremental issuance has been filed "
                 "since.")
    else:
        headline = "Oxford Lane's ATM program has raised over a billion dollars at a persistent premium to NAV."
        notes = ("Every observed premium is positive, but premium size vs. issuance size correlates weakly (r≈-0.30, not shown) — "
                 "issuance has scaled up over time more than it has tracked period-to-period premium swings.")

    png, svg = save_figure(
        fig, "viz_flywheel",
        headline=headline,
        subtitle="Premium/(discount) to disclosed NAV, incremental at-the-market share issuance, and cumulative net proceeds raised, "
                 "Oxford Lane Capital Corp. (OXLC), 2016-present.",
        source="clo-atlas, from OXLC's EDGAR 424B3/497 ATM supplements, OXLC's own NAV-update press releases (GlobeNewswire), "
                "and Yahoo Finance prices",
        notes=notes,
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_flywheel()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
