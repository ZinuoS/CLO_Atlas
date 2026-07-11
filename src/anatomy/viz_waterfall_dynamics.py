"""Waterfall "dynamics" via static PNGs — no HTML app, no Playwright. Four
techniques, all built on one shared, fixed-geometry tollbooth layout so that
a viewer can click through PNGs frame-by-frame in PowerPoint and perceive
motion from data changes alone, never from the diagram jumping around:

  1. Click-through frame sequences (this module's `build_click_through`):
     3-6 PNGs of the same interest-waterfall tollbooth at successive key
     quarters. Every static element (figure size, axes rect/limits, node
     boxes, fonts, margins) is byte-for-byte the same Python constant across
     every frame; only fill colors, arrow highlights, and the numbers/text
     inside boxes are data-driven. Enforced by
     tests_viz_waterfall_dynamics.py, which renders two frames and asserts
     every static element's pixel position (via matplotlib's own
     transData/transFigure transforms) is identical.
  2. Ghost overlay (`build_ghost_overlay`): the base-case flow in light warm
     gray underneath, the scenario's flow in full color on top.
  3. Waterfall-through-time matrix (`build_time_matrix`): priority stops as
     rows, quarters as columns, cell shading = cash received.
  4. Allocation stream (`build_allocation_stream`): stacked area of where
     each quarter's collections went.

Every export is 1920x1080 px by construction (figsize (12.8, 7.2) @ dpi 150)
— there is no separate "standalone key frame" render path; every frame in a
sequence already meets that spec, so exporting one is just picking a file.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

import config
from src.anatomy.deal import Deal, load_deal
from src.anatomy.scenarios import Scenario, build_scenarios, run_scenario
from src.common.style import ACCENT, ACCENT_SOFT, BG, INK, INK_MUTED, WARM_GRAY, apply_theme, save_figure

# ---------------------------------------------------------------------------
# Fixed geometry — every constant below is shared by every frame this module
# ever renders. Nothing here may depend on scenario, period, or text length.
# ---------------------------------------------------------------------------
FIGSIZE_IN = (12.8, 7.2)   # x DPI = 1920x1080 px, the deliverable pixel size
DPI = 150
AX_RECT = (0.06, 0.16, 0.66, 0.70)   # left, bottom, width, height (figure fraction)
XLIM = (0.0, 10.0)
YLIM = (1.6, 13.4)

NODE_X0, NODE_W, NODE_H = 0.6, 6.6, 0.66

# (key, label, y_center, test_level or None)
NODES: tuple[tuple[str, str, float, str | None], ...] = (
    ("senior_expenses", "Senior expenses & admin cap", 12.4, None),
    ("senior_mgmt_fee", "Senior management fee", 11.4, None),
    ("AAA_interest", "AAA interest", 10.4, None),
    ("AA_interest", "AA interest  +  AAA/AA joint coverage tests", 9.4, "AA"),
    ("A_interest", "A interest  +  A coverage tests", 8.4, "A"),
    ("BBB_interest", "BBB interest  +  BBB coverage tests", 7.4, "BBB"),
    ("BB_interest", "BB interest  +  BB OC test", 6.4, "BB"),
    ("interest_diversion_test", "Interest diversion test (reinvestment only)", 5.4, None),
    ("sub_mgmt_fee", "Subordinated management fee", 4.4, None),
    ("incentive_fee", "Incentive fee (over hurdle)", 3.4, None),
    ("equity_residual_interest", "Residual cash to equity", 2.4, None),
)
NODE_Y = {key: y for key, _, y, _ in NODES}

CURE_BOX = dict(x=7.7, y=9.9, w=1.7, h=2.0,
                label="Cure:\ndiverted interest\npays down\nAAA/AA principal")
CURE_STUB_X = (NODE_X0 + NODE_W, CURE_BOX["x"])
CURE_TEST_LEVELS = ("AA", "A", "BBB", "BB")

FONT_NODE_LABEL = 8.6
FONT_NODE_AMOUNT = 8.0
FONT_HEADLINE = 14
FONT_STEP = 10
FONT_CAPTION = 10
FONT_FOOTER = 7.5


def _stop(row: pd.Series, category: str, name: str) -> float:
    val = row.get(f"stop_{category}_{name}", 0.0)
    return 0.0 if pd.isna(val) else float(val)


def _period_label(deal: Deal, period: int) -> str:
    d = deal.dates
    if period <= d.non_call_end_quarter:
        phase = "non-call"
    elif period <= d.reinvestment_end_quarter:
        phase = "reinvestment"
    else:
        phase = "amortization"
    return f"Q{period} ({phase})"


def select_key_frames(df: pd.DataFrame, max_frames: int = 5) -> list[int]:
    """Pick `max_frames` periods that tell the scenario's story: a calm
    period before anything happens, the first breach, the worst period,
    the first cure, and a steady period afterward. Falls back to evenly
    spaced periods when nothing breaches (e.g. the base case)."""
    test_cols = [c for c in df.columns if c.startswith("oc_pass_")]
    any_fail = ~df[test_cols].all(axis=1) if test_cols else pd.Series(False, index=df.index)
    periods = df["period"].tolist()

    if not any_fail.any():
        idx = np.linspace(0, len(df) - 1, num=min(max_frames, len(df)), dtype=int)
        return sorted(set(periods[i] for i in idx))

    fail_idx = df.index[any_fail]
    first_fail, last_fail = fail_idx[0], fail_idx[-1]
    n_fails_by_row = (~df[test_cols]).sum(axis=1)
    worst_idx = n_fails_by_row.idxmax()
    calm_idx = max(0, first_fail - 1)
    cure_candidates = df.index[(df.index > last_fail)]
    cure_idx = cure_candidates[0] if len(cure_candidates) else last_fail
    steady_candidates = df.index[df.index > cure_idx + 4]
    steady_idx = steady_candidates[0] if len(steady_candidates) else df.index[-1]

    picks = [calm_idx, first_fail, worst_idx, cure_idx, steady_idx]
    picks = sorted(set(int(p) for p in picks))[:max_frames]
    return [int(df.loc[i, "period"]) for i in picks]


def _draw_box(ax, x, y, w, h, label, fill, edge=INK, text_color=INK, fontsize=FONT_NODE_LABEL, lw=1.1):
    box = FancyBboxPatch((x, y - h / 2), w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
                          facecolor=fill, edgecolor=edge, linewidth=lw, zorder=2)
    ax.add_patch(box)
    ax.text(x + w / 2, y, label, ha="center", va="center", fontsize=fontsize, color=text_color, zorder=3, wrap=True)
    return box


def render_frame(deal: Deal, scenario: Scenario, row: pd.Series, step_idx: int, n_steps: int) -> plt.Figure:
    """Render one click-through frame. `row` is one period's tidy record
    from `run_scenario`. Geometry is 100% constants above; only fill
    colors and text content read from `row`."""
    apply_theme()
    fig = plt.figure(figsize=FIGSIZE_IN, dpi=DPI, facecolor=BG)
    ax = fig.add_axes(AX_RECT)
    ax.set_xlim(*XLIM)
    ax.set_ylim(*YLIM)
    ax.axis("off")

    period = int(row["period"])

    for key, label, y, test_level in NODES:
        amount = _stop(row, "interest_diversion" if key == "interest_diversion_test" else "interest", key)
        passing = bool(row.get(f"oc_pass_{test_level}", True)) if test_level else True
        if not passing:
            fill = ACCENT_SOFT
        elif amount > 0:
            fill = WARM_GRAY[3]
        else:
            fill = "#F5F3EF"
        _draw_box(ax, NODE_X0, y, NODE_W, NODE_H, "", fill)
        ax.text(NODE_X0 + 0.18, y + 0.10, label, ha="left", va="center", fontsize=FONT_NODE_LABEL, color=INK)
        ax.text(NODE_X0 + NODE_W - 0.18, y - 0.14, f"${amount:,.0f}", ha="right", va="center",
                fontsize=FONT_NODE_AMOUNT, color=INK_MUTED, fontweight="medium")
        if test_level:
            tag = "PASS" if passing else "FAIL"
            tag_color = INK_MUTED if passing else ACCENT
            ax.text(NODE_X0 + NODE_W - 0.18, y + 0.13, tag, ha="right", va="center",
                    fontsize=7, color=tag_color, fontweight="bold")

    # Arrows connecting consecutive stops top-to-bottom, fixed positions.
    ys = [y for _, _, y, _ in NODES]
    for y_top, y_bot in zip(ys[:-1], ys[1:]):
        ax.add_patch(FancyArrowPatch((NODE_X0 + NODE_W / 2, y_top - NODE_H / 2 - 0.01),
                                      (NODE_X0 + NODE_W / 2, y_bot + NODE_H / 2 + 0.01),
                                      arrowstyle="-|>", mutation_scale=8, color=INK_MUTED, lw=0.9, zorder=1))

    # Cure box + fixed stub arrows from each test level (always drawn; only
    # color/label are data-driven).
    total_cure = sum(_stop(row, "interest_diversion", f"divert_to_{lvl}_cure") for lvl in CURE_TEST_LEVELS)
    cure_fill = ACCENT if total_cure > 0 else "#F5F3EF"
    _draw_box(ax, CURE_BOX["x"], CURE_BOX["y"], CURE_BOX["w"], CURE_BOX["h"], "", cure_fill,
              text_color=BG if total_cure > 0 else INK_MUTED)
    ax.text(CURE_BOX["x"] + CURE_BOX["w"] / 2, CURE_BOX["y"], CURE_BOX["label"], ha="center", va="center",
            fontsize=7.6, color=(BG if total_cure > 0 else INK_MUTED), zorder=3)
    if total_cure > 0:
        ax.text(CURE_BOX["x"] + CURE_BOX["w"] / 2, CURE_BOX["y"] - CURE_BOX["h"] / 2 - 0.28,
                f"${total_cure:,.0f} diverted", ha="center", va="center", fontsize=7.6, color=ACCENT, fontweight="bold")
    for lvl in CURE_TEST_LEVELS:
        amt = _stop(row, "interest_diversion", f"divert_to_{lvl}_cure")
        active = amt > 0
        ax.add_patch(FancyArrowPatch((CURE_STUB_X[0], NODE_Y[f"{lvl}_interest"]),
                                      (CURE_STUB_X[1], NODE_Y[f"{lvl}_interest"]),
                                      arrowstyle="-|>", mutation_scale=8,
                                      color=ACCENT if active else "#D8D2C6",
                                      lw=1.6 if active else 0.7, zorder=1))

    # Fixed-position text bands (content varies, positions never do).
    fig.text(0.06, 0.955, scenario.thesis, fontsize=FONT_HEADLINE, fontweight="bold", color=INK, ha="left", va="top", wrap=True)
    fig.text(0.94, 0.955, f"Frame {step_idx} of {n_steps}", fontsize=FONT_STEP, color=INK_MUTED, ha="right", va="top")
    fig.text(0.06, 0.905, f"{_period_label(deal, period)}  ·  CDR {row['cdr_pct']:.1f}%  ·  CPR {row['cpr_pct']:.1f}%  ·  "
                          f"recovery {row['recovery_rate_pct']:.0f}%  ·  SOFR {row['sofr_pct']:.2f}%",
             fontsize=FONT_CAPTION, color=INK_MUTED, ha="left", va="top")
    caption = _frame_caption(row)
    fig.text(0.06, 0.865, caption, fontsize=FONT_CAPTION, color=INK, ha="left", va="top", style="italic")

    # Right-hand summary panel: equity distribution + tranche balances.
    fig.text(0.755, 0.86, "This quarter", fontsize=10, fontweight="bold", color=INK, ha="left", va="top")
    fig.text(0.755, 0.815, f"Equity distribution: ${row['equity_distribution']:,.0f}", fontsize=8.6, color=INK_MUTED, ha="left", va="top")
    fig.text(0.755, 0.785, f"Reinvesting: {'yes' if row['reinvesting'] else 'no'}", fontsize=8.6, color=INK_MUTED, ha="left", va="top")

    source = deal.citation.get("deal_name", "")
    fig.text(0.06, 0.045, f"SOURCE: STRUCTURE ILLUSTRATIVE, PARAMETERS ADAPTED FROM {source.upper()}, "
                          "PUBLIC OFFERING CIRCULAR", fontsize=FONT_FOOTER, color=INK_MUTED, ha="left", va="bottom")
    fig.text(0.94, 0.045, "Credit: Ashley Shi", fontsize=FONT_FOOTER, color=INK_MUTED, ha="right", va="bottom")
    fig.text(0.06, 0.02, "Model simplifications: single simplified BSL structure (2 collapsed sub-classes per "
                         "original class, non-economic overlay note dropped); no explicit EOD/acceleration path; "
                         "CCC excess haircut and recovery-lag conventions are TO-VERIFY market assumptions, not "
                         "deal terms.", fontsize=6.4, color=INK_MUTED, ha="left", va="bottom", style="italic")

    return fig


def _frame_caption(row: pd.Series) -> str:
    test_cols = [c for c in row.index if c.startswith("oc_pass_")]
    failing = [c.replace("oc_pass_", "") for c in test_cols if not row[c]]
    if failing:
        return f"Coverage test(s) failing this quarter: {', '.join(failing)} — interest diverts to cure senior principal."
    if row["equity_distribution"] <= 0.01:
        return "All tests pass, but every dollar of interest is exhausted before reaching equity this quarter."
    return "Every coverage test passes; cash flows through the full stack to equity as designed."


def build_click_through(deal: Deal, scenario_key: str, max_frames: int = 5,
                         out_dir: Path | None = None) -> list[Path]:
    out_dir = Path(out_dir or config.FIGURES_ANATOMY_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    scenarios = build_scenarios(deal)
    scenario = scenarios[scenario_key]
    df = run_scenario(deal, scenario)
    periods = select_key_frames(df, max_frames=max_frames)
    n = len(periods)

    paths = []
    for k, period in enumerate(periods, start=1):
        row = df[df["period"] == period].iloc[0]
        fig = render_frame(deal, scenario, row, step_idx=k, n_steps=n)
        path = out_dir / f"waterfall_{scenario_key}_f{k}of{n}.png"
        fig.savefig(path, dpi=DPI, facecolor=BG)
        plt.close(fig)
        paths.append(path)

    if config.ANATOMY_BUILD_GIFS and paths:
        _assemble_gif(paths, out_dir / f"waterfall_{scenario_key}.gif")
    return paths


def _assemble_gif(frame_paths: list[Path], out_path: Path, duration_ms: int = 1200) -> None:
    """Optional reviewing convenience. Never used to decide frame count,
    spacing, or layout — those are fixed by `select_key_frames`/geometry
    constants regardless of whether a GIF is ever built."""
    from PIL import Image
    frames = [Image.open(p).convert("RGB") for p in frame_paths]
    frames[0].save(out_path, save_all=True, append_images=frames[1:], duration=duration_ms, loop=0)


ALL_SCENARIO_KEYS = ("base", "covid_shock", "severe_recession", "post_reinvestment_amortization",
                     "rate_shock_up", "rate_shock_down")
SHOCK_SCENARIO_KEYS = tuple(k for k in ALL_SCENARIO_KEYS if k != "base")


def _node_amount(row: pd.Series, key: str) -> float:
    category = "interest_diversion" if key == "interest_diversion_test" else "interest"
    return _stop(row, category, key)


def _worst_period(df: pd.DataFrame) -> int:
    test_cols = [c for c in df.columns if c.startswith("oc_pass_")]
    if not test_cols:
        return int(df["period"].iloc[len(df) // 2])
    n_fails = (~df[test_cols]).sum(axis=1)
    return int(df.loc[n_fails.idxmax(), "period"])


# ---------------------------------------------------------------------------
# Technique 2: before/after ghost overlay
# ---------------------------------------------------------------------------
def build_ghost_overlay(deal: Deal, scenario_key: str, period: int | None = None,
                         out_dir: Path | None = None) -> Path:
    """Base-case flow (light warm gray, behind) vs. this scenario's flow
    (full color, in front) at one quarter. Divergence is the only saturated
    element — a stop that matches the base case stays neutral gray."""
    out_dir = Path(out_dir or config.FIGURES_ANATOMY_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    scenarios = build_scenarios(deal)
    df_base = run_scenario(deal, scenarios["base"])
    df_scenario = run_scenario(deal, scenarios[scenario_key])
    if period is None:
        period = _worst_period(df_scenario)
    row_base = df_base[df_base["period"] == period].iloc[0]
    row_scenario = df_scenario[df_scenario["period"] == period].iloc[0]

    apply_theme()
    fig = plt.figure(figsize=FIGSIZE_IN, dpi=DPI, facecolor=BG)
    ax = fig.add_axes(AX_RECT)
    ax.set_xlim(*XLIM)
    ax.set_ylim(*YLIM)
    ax.axis("off")

    bar_h = NODE_H * 0.32
    for key, label, y, _level in NODES:
        base_amt = _node_amount(row_base, key)
        scen_amt = _node_amount(row_scenario, key)
        ref = max(base_amt, scen_amt, 1.0)
        _draw_box(ax, NODE_X0, y, NODE_W, NODE_H, "", "#FAFAF8")
        ax.text(NODE_X0 + 0.18, y + NODE_H / 2 - 0.14, label, ha="left", va="center", fontsize=FONT_NODE_LABEL, color=INK)
        bar_x0 = NODE_X0 + 0.18
        bar_w_max = NODE_W - 0.36
        # Ghost (base case), behind, light warm gray.
        ax.add_patch(plt.Rectangle((bar_x0, y - NODE_H / 2 + 0.10), bar_w_max * (base_amt / ref), bar_h,
                                    facecolor=WARM_GRAY[3], edgecolor="none", zorder=2))
        # Scenario, in front, drawn thinner and inset so both are visible;
        # saturated (ACCENT) only when it falls meaningfully short of base.
        diverges = scen_amt < base_amt * 0.98
        scen_color = ACCENT if diverges else WARM_GRAY[0]
        ax.add_patch(plt.Rectangle((bar_x0, y - NODE_H / 2 + 0.10), bar_w_max * (scen_amt / ref), bar_h * 0.55,
                                    facecolor=scen_color, edgecolor="none", zorder=3))
        ax.text(NODE_X0 + NODE_W - 0.18, y - NODE_H / 2 + 0.10 + bar_h + 0.06,
                f"base \\${base_amt:,.0f}  vs  scenario \\${scen_amt:,.0f}", ha="right", va="bottom",
                fontsize=7.2, color=(ACCENT if diverges else INK_MUTED))

    scenario = scenarios[scenario_key]
    fig.text(0.06, 0.955, f"Where {scenario_key.replace('_', ' ')} diverges from the base case", fontsize=FONT_HEADLINE,
              fontweight="bold", color=INK, ha="left", va="top", wrap=True)
    fig.text(0.06, 0.905, f"{_period_label(deal, period)}  ·  {scenario.thesis}", fontsize=FONT_CAPTION,
              color=INK_MUTED, ha="left", va="top", wrap=True)
    source = deal.citation.get("deal_name", "")
    fig.text(0.06, 0.045, f"SOURCE: STRUCTURE ILLUSTRATIVE, PARAMETERS ADAPTED FROM {source.upper()}, "
                          "PUBLIC OFFERING CIRCULAR", fontsize=FONT_FOOTER, color=INK_MUTED, ha="left", va="bottom")
    fig.text(0.94, 0.045, "Credit: Ashley Shi", fontsize=FONT_FOOTER, color=INK_MUTED, ha="right", va="bottom")

    path = out_dir / f"waterfall_ghost_{scenario_key}.png"
    fig.savefig(path, dpi=DPI, facecolor=BG)
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Technique 3: waterfall-through-time matrix
# ---------------------------------------------------------------------------
def build_time_matrix(deal: Deal, scenario_key: str, out_dir: Path | None = None) -> Path:
    """Priority stops as rows, quarters as columns; cell shading = cash
    received that quarter, normalized per-row (scales differ by orders of
    magnitude between, e.g., AAA interest and the incentive fee). Quarters
    where any coverage test fails get an accent underline."""
    out_dir = Path(out_dir or config.FIGURES_ANATOMY_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    scenarios = build_scenarios(deal)
    scenario = scenarios[scenario_key]
    df = run_scenario(deal, scenario)

    row_keys = [key for key, _l, _y, _lv in NODES]
    row_labels = [label for _k, label, _y, _lv in NODES]
    matrix = np.zeros((len(row_keys), len(df)))
    for i, key in enumerate(row_keys):
        vals = np.array([_node_amount(r, key) for _, r in df.iterrows()])
        row_max = vals.max()
        matrix[i] = vals / row_max if row_max > 0 else vals

    test_cols = [c for c in df.columns if c.startswith("oc_pass_")]
    breach_mask = (~df[test_cols]).any(axis=1).to_numpy() if test_cols else np.zeros(len(df), dtype=bool)

    apply_theme()
    cmap = mpl_colors_cmap()
    fig, ax = plt.subplots(figsize=(13, 6.2), facecolor=BG)
    fig.subplots_adjust(left=0.24)
    im = ax.imshow(matrix, aspect="auto", cmap=cmap, vmin=0, vmax=1, interpolation="nearest")
    ax.set_yticks(range(len(row_labels)))
    ax.set_yticklabels(row_labels, fontsize=8.5)
    xticks = np.arange(0, len(df), max(1, len(df) // 13))
    ax.set_xticks(xticks)
    ax.set_xticklabels([f"Q{int(df['period'].iloc[i])}" for i in xticks], fontsize=8)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0)

    y0 = len(row_labels) - 0.5
    for i, breached in enumerate(breach_mask):
        if breached:
            ax.add_patch(plt.Rectangle((i - 0.5, y0), 1, 0.28, facecolor=ACCENT, edgecolor="none", clip_on=False))
    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("share of that row's peak quarterly cash received", fontsize=8, color=INK_MUTED)
    cbar.ax.tick_params(labelsize=7)

    png, svg = save_figure(
        fig, f"waterfall_matrix_{scenario_key}",
        headline=f"Cash through the waterfall, quarter by quarter — {scenario_key.replace('_', ' ')}.",
        subtitle=scenario.thesis + " Red tick marks below the axis flag quarters with any coverage-test breach.",
        source=f"structure illustrative, parameters adapted from {deal.citation.get('deal_name', '')}, public offering circular",
        notes="Each row is normalized to its own peak quarterly cash — rows are not comparable to each other in absolute dollars.",
        out_dir=out_dir,
    )
    return png


def mpl_colors_cmap():
    from matplotlib.colors import LinearSegmentedColormap
    return LinearSegmentedColormap.from_list("clo_atlas_sequential", ["#FAFAF8", ACCENT])


# ---------------------------------------------------------------------------
# Technique 4: allocation stream (stacked area, scenario small multiples)
# ---------------------------------------------------------------------------
def build_allocation_stream(deal: Deal, scenario_keys: tuple[str, ...] = ALL_SCENARIO_KEYS,
                             out_dir: Path | None = None) -> Path:
    """For each scenario, a stacked area of where every quarter's interest
    collections went (as a share of that quarter's total), small multiples
    across scenarios so the shift in allocation under stress is directly
    comparable."""
    out_dir = Path(out_dir or config.FIGURES_ANATOMY_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    scenarios = build_scenarios(deal)

    stream_keys = ["AAA_interest", "AA_interest", "A_interest", "BBB_interest", "BB_interest",
                   "interest_diversion_test", "equity_residual_interest"]
    stream_labels = ["AAA", "AA", "A", "BBB", "BB", "divert to collateral", "equity"]
    colors = [WARM_GRAY[3], WARM_GRAY[2], WARM_GRAY[1], WARM_GRAY[0], "#9A5B5B", "#C9924E", ACCENT]

    apply_theme()
    ncols = 3
    nrows = -(-len(scenario_keys) // ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(15, 4.3 * nrows + 0.6), facecolor=BG, sharex=True, sharey=True,
                              gridspec_kw={"hspace": 0.45})
    axes_flat = axes.flatten() if len(scenario_keys) > 1 else [axes]

    for ax, key in zip(axes_flat, scenario_keys):
        df = run_scenario(deal, scenarios[key])
        total = sum(df[f"stop_interest_{k}"].fillna(0.0) if k != "interest_diversion_test"
                    else df.get("stop_interest_diversion_interest_diversion_test", pd.Series(0.0, index=df.index)).fillna(0.0)
                    for k in stream_keys)
        total = total.replace(0, np.nan)
        shares = []
        for k in stream_keys:
            col = (df.get("stop_interest_diversion_interest_diversion_test", pd.Series(0.0, index=df.index))
                   if k == "interest_diversion_test" else df.get(f"stop_interest_{k}", pd.Series(0.0, index=df.index)))
            shares.append((col.fillna(0.0) / total).fillna(0.0).to_numpy())
        ax.stackplot(df["period"], shares, colors=colors, labels=stream_labels, linewidth=0)
        ax.set_title(key.replace("_", " "), fontsize=10, fontweight="bold", color=INK, loc="left")
        ax.set_ylim(0, 1)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)

    for ax in axes_flat[len(scenario_keys):]:
        ax.axis("off")

    from matplotlib.patches import Patch
    handles = [Patch(facecolor=c, label=lbl) for c, lbl in zip(colors, stream_labels)]

    # save_figure() reserves fixed header/footer bands but knows nothing
    # about a legend row, so the legend is placed manually in the gap
    # between the two panel rows (reserved above via gridspec hspace) and
    # save_figure's own subplots_adjust(top=..., bottom=...) call — which
    # only touches top/bottom, never hspace — is left free to run after.
    fig.legend(handles=handles, loc="center", bbox_to_anchor=(0.5, 0.505), ncol=7, fontsize=8.5, frameon=False)

    png, svg = save_figure(
        fig, "waterfall_allocation_stream",
        headline="Where each quarter's interest collections go, by scenario.",
        subtitle="Share of interest collections allocated to each stop in the waterfall, base case vs. every stress scenario.",
        source=f"structure illustrative, parameters adapted from {deal.citation.get('deal_name', '')}, public offering circular",
        out_dir=out_dir,
    )
    return png


def main():
    result = run()
    for scenario_key, paths in result["click_through"].items():
        print(f"{scenario_key}: wrote {len(paths)} frames")
        for p in paths:
            print(f"  {p}")
    for scenario_key, path in result["ghost_overlay"].items():
        print(f"ghost overlay {scenario_key}: {path}")
    for scenario_key, path in result["time_matrix"].items():
        print(f"time matrix {scenario_key}: {path}")
    print(f"allocation stream: {result['allocation_stream']}")


def run(deal: Deal | None = None) -> dict:
    deal = deal or load_deal()
    return {
        "click_through": {key: build_click_through(deal, key) for key in ALL_SCENARIO_KEYS},
        "ghost_overlay": {key: build_ghost_overlay(deal, key) for key in SHOCK_SCENARIO_KEYS},
        "time_matrix": {key: build_time_matrix(deal, key) for key in SHOCK_SCENARIO_KEYS},
        "allocation_stream": build_allocation_stream(deal),
    }


if __name__ == "__main__":
    main()
