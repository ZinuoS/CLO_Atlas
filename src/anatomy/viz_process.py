"""The arranger-process lifecycle, in two complementary variants:

  1. `build_lifecycle_timeline`: phases plotted against the stylized deal's
     own quarter axis (deal.dates), so "non-call ends," "reinvestment ends,"
     and "stated maturity" are this project's actual modeled dates, not
     generic placeholders. Pre-closing sub-phases (mandate/ramp/structuring/
     syndication) aren't in the circular at all — it only discloses the
     warehouse-open-to-closing span — so they're illustrative slices of
     that span, tagged TO-VERIFY on the figure itself.
  2. `build_lifecycle_parties`: a phase x party matrix showing who is
     actually at the table at each stage and what they're doing there,
     which the timeline alone can't convey.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import config
from src.anatomy.deal import Deal, load_deal
from src.common.style import ACCENT, BG, INK, INK_MUTED, WARM_GRAY, apply_theme, save_figure

# ---------------------------------------------------------------------------
# Variant 1: timeline
#
# The pre-closing steps (mandate through pricing) span just 3 quarters in
# our modeled deal while the post-closing life spans 52 — a single linear
# quarter axis would crush the pre-closing steps to invisibility. Since the
# circular doesn't disclose real dates for those internal steps anyway
# (TO-VERIFY territory regardless), they're drawn as equal-width sequential
# STEPS on their own panel, and only the post-closing phases — which do
# have real modeled quarter numbers — get the true time-proportional axis.
# ---------------------------------------------------------------------------
def build_lifecycle_timeline(deal: Deal, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir or config.FIGURES_ANATOMY_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    d = deal.dates

    apply_theme()
    fig, (ax_pre, ax_post) = plt.subplots(1, 2, figsize=(14, 4.6), facecolor=BG, gridspec_kw={"width_ratios": [1, 2.4]})

    pre_steps = ["Mandate", "Warehouse\n& ramp", "Structuring", "Syndication", "Pricing", "Closing"]
    n = len(pre_steps)
    for i, step in enumerate(pre_steps):
        color = ACCENT if step == "Closing" else WARM_GRAY[min(i, 3)]
        text_color = BG if step == "Closing" else INK
        ax_pre.add_patch(plt.Rectangle((i, 0), 1.0, 1, facecolor=color, edgecolor=BG, linewidth=1.5))
        ax_pre.text(i + 0.5, 0.5, step, ha="center", va="center", fontsize=7.6, color=text_color)
    ax_pre.set_xlim(0, n)
    ax_pre.set_ylim(-0.35, 1.35)
    ax_pre.axis("off")
    ax_pre.set_title("Before closing (steps, not to scale)", fontsize=8.5, color=INK_MUTED, loc="left")

    bands = [
        (d.closing_quarter, d.non_call_end_quarter, "#C9924E", "Non-call"),
        (d.non_call_end_quarter, d.reinvestment_end_quarter, WARM_GRAY[2], "Reinvestment"),
        (d.reinvestment_end_quarter, d.stated_maturity_quarter, WARM_GRAY[3], "Amortization"),
    ]
    for start, end, color, label in bands:
        ax_post.add_patch(plt.Rectangle((start, 0), end - start, 1, facecolor=color, edgecolor=BG, linewidth=1.5))
        ax_post.text((start + end) / 2, 0.5, label, ha="center", va="center", fontsize=9,
                     color=(BG if color == "#C9924E" else INK))
    markers = [
        (d.closing_quarter, "Closing / effective date"),
        (d.non_call_end_quarter, "Non-call ends"),
        (d.reinvestment_end_quarter, "Reinvestment ends"),
        (d.stated_maturity_quarter, "Stated maturity"),
    ]
    for q, _label in markers:
        ax_post.axvline(q, color=INK, lw=0.9, ymin=0, ymax=1, clip_on=False)
    ax_post.set_xlim(d.closing_quarter - 1, d.stated_maturity_quarter + 1)
    ax_post.set_ylim(-0.1, 1.1)
    ax_post.set_xticks([q for q, _l in markers])
    ax_post.set_xticklabels([f"{lbl}\nQ{q}" for q, lbl in markers], fontsize=7.6, color=INK)
    for spine in ax_post.spines.values():
        spine.set_visible(False)
    ax_post.get_yaxis().set_visible(False)
    ax_post.tick_params(axis="x", length=0, pad=8)
    ax_post.set_title("After closing (true quarter axis)", fontsize=8.5, color=INK_MUTED, loc="left")

    fig.subplots_adjust(top=0.68, wspace=0.15)

    png, svg = save_figure(
        fig, "process_lifecycle_timeline",
        headline="An arranger's-eye view of the deal's life.",
        subtitle="Left: the pre-closing process as sequential steps (the circular doesn't date these internally). "
                  "Right: non-call, reinvestment, and maturity on this project's real modeled quarter axis.",
        source=f"structure illustrative, parameters adapted from {deal.citation.get('deal_name', '')}, public offering circular",
        notes="TO-VERIFY: the circular discloses only the warehouse-open and closing dates for the pre-closing span, "
              "not the mandate/structuring/syndication milestones shown at left.",
        out_dir=out_dir,
    )
    return png


# ---------------------------------------------------------------------------
# Variant 2: parties / roles matrix
# ---------------------------------------------------------------------------
PHASES = ("Warehouse & ramp", "Structuring & rating review", "Syndication & pricing",
          "Closing", "Reinvestment", "Amortization")

PARTIES: tuple[tuple[str, dict[str, str]], ...] = (
    ("Arranger / bookrunner bank", {
        "Warehouse & ramp": "provides warehouse facility, sources loans",
        "Structuring & rating review": "structures tranches, liaises with agencies",
        "Syndication & pricing": "markets and prices the notes",
        "Closing": "takes out warehouse loan at closing",
    }),
    ("Collateral manager", {
        "Warehouse & ramp": "selects & buys loans into the warehouse",
        "Structuring & rating review": "sets eligibility criteria & concentration limits",
        "Reinvestment": "trades the portfolio within tests",
        "Amortization": "runs off collateral, no further reinvestment",
    }),
    ("Rating agencies", {
        "Structuring & rating review": "assigns expected ratings to each class",
        "Reinvestment": "surveils ratings as collateral migrates",
        "Amortization": "surveils ratings through paydown",
    }),
    ("Trustee", {
        "Closing": "holds collateral, administers accounts",
        "Reinvestment": "runs the waterfall, calculates OC/IC tests",
        "Amortization": "runs the waterfall, calculates OC/IC tests",
    }),
    ("Senior investors (AAA/AA)", {
        "Syndication & pricing": "buy at par, set the floating spread",
        "Reinvestment": "receive interest; principal money-good",
        "Amortization": "receive amortizing principal first",
    }),
    ("Mezz investors (A-BB)", {
        "Syndication & pricing": "buy at par or discount",
        "Reinvestment": "interest can PIK if tests fail",
        "Amortization": "paid sequentially after senior classes",
    }),
    ("Equity investors", {
        "Warehouse & ramp": "often fund first-loss warehouse capital",
        "Closing": "fund the equity tranche at closing",
        "Reinvestment": "receive residual cash; first to be cut off",
        "Amortization": "receive residual cash after debt fully repaid",
    }),
)


def build_lifecycle_parties(deal: Deal, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir or config.FIGURES_ANATOMY_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    apply_theme()
    fig, ax = plt.subplots(figsize=(14, 7.2), facecolor=BG)
    n_rows, n_cols = len(PARTIES), len(PHASES)
    col_w, row_h = 1.0, 1.0

    for c, phase in enumerate(PHASES):
        ax.text(c * col_w + col_w / 2, n_rows + 0.3, phase, ha="center", va="bottom", fontsize=8.6,
                fontweight="bold", color=INK, rotation=12)

    for r, (party, roles) in enumerate(PARTIES):
        y = n_rows - 1 - r
        ax.text(-0.15, y + row_h / 2, party, ha="right", va="center", fontsize=9, color=INK)
        for c, phase in enumerate(PHASES):
            active = phase in roles
            fill = WARM_GRAY[3] if active else "#FAFAF8"
            ax.add_patch(plt.Rectangle((c * col_w, y), col_w, row_h, facecolor=fill, edgecolor=BG, linewidth=1.5))
            if active:
                wrapped = "\n".join(textwrap.wrap(roles[phase], width=15))
                ax.text(c * col_w + col_w / 2, y + row_h / 2, wrapped, ha="center", va="center",
                        fontsize=6.6, color=INK)

    ax.set_xlim(-2.3, n_cols * col_w)
    ax.set_ylim(0, n_rows + 1.3)
    ax.axis("off")

    png, svg = save_figure(
        fig, "process_lifecycle_parties",
        headline="Who is actually at the table, and when.",
        subtitle="Each cell is that party's role in that phase of the deal's life; a blank cell means they aren't active then.",
        source=f"structure illustrative, parameters adapted from {deal.citation.get('deal_name', '')}, public offering circular",
        notes="Roles are standard CLO market practice, not terms drawn from the circular itself.",
        out_dir=out_dir,
    )
    return png


def main():
    deal = load_deal()
    print(f"wrote {build_lifecycle_timeline(deal)}")
    print(f"wrote {build_lifecycle_parties(deal)}")


if __name__ == "__main__":
    main()
