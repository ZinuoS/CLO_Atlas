"""NYT-style chart theming: apply_theme() for matplotlib, save_figure() for the
headline/subtitle/source/annotation scaffold every figure in this project uses,
plus an Altair theme for the interactive HTML counterparts.

House rules (do not deviate per-chart):
  - Off-white background (#FAF9F6), horizontal-only gridlines, no top/right spines.
  - Direct labeling at line ends instead of a legend box whenever series <= 6.
  - One accent color against a warm-gray categorical ramp; color means something
    (the thing the chart is about) or it isn't used at all.
  - Headline is a full declarative sentence in bold; subtitle carries the
    technical description; source line bottom-left in small caps; byline+date
    bottom-right.
  - Categorical hues are assigned in a FIXED order (never cycled/regenerated per
    filter) so an entity keeps its color across every chart it appears in.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

import matplotlib as mpl
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

import config

# ---------------------------------------------------------------------------
# Palette — one accent, a warm-gray categorical ramp (fixed order, never cycled),
# a two-hue diverging pair for polarity charts, off-white surface.
# ---------------------------------------------------------------------------
BG = "#FAF9F6"
INK = "#1A1A1A"
INK_MUTED = "#5C5652"
GRID = "#DAD5CE"
ACCENT = "#D0021B"          # the one color that "means something" per chart
ACCENT_SOFT = "#F2A6AE"     # accent tint, for shaded spans/uncertainty bands
WARM_GRAY = ["#4A4540", "#8C8579", "#B8B0A4", "#D8D2C6"]  # fixed categorical order
DIVERGING = ("#2A6F97", "#D0021B")  # cool pole, warm pole; neutral midpoint = WARM_GRAY[2]
EVENT_SPAN = "#C7C0B4"

BYLINE = f"{config.CONTACT_NAME}"

_FONT_CANDIDATES = ["Georgia", "Charter", "Times New Roman", "DejaVu Serif"]


def apply_theme() -> None:
    """Call once at the top of any script/notebook before plotting."""
    available = {f.name for f in mpl.font_manager.fontManager.ttflist}
    serif = next((f for f in _FONT_CANDIDATES if f in available), "DejaVu Serif")
    mpl.rcParams.update({
        "figure.facecolor": BG,
        "axes.facecolor": BG,
        "savefig.facecolor": BG,
        "font.family": serif,
        "text.color": INK,
        "axes.edgecolor": INK_MUTED,
        "axes.labelcolor": INK_MUTED,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": INK_MUTED,
        "ytick.color": INK_MUTED,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "axes.titlesize": 13,
        "axes.labelsize": 10,
        "legend.frameon": False,
        "lines.linewidth": 2.0,
        "figure.dpi": 150,
    })


def categorical_color(index: int) -> str:
    """Fixed-order categorical color. index 0 is always the accent; 1-3 are the
    warm-gray ramp; index >= 4 folds into a repeating muted tail rather than
    inventing new hues (per project rule: a 9th series is never a generated hue)."""
    if index == 0:
        return ACCENT
    ramp = WARM_GRAY
    return ramp[(index - 1) % len(ramp)]


def direct_label(ax, x, y, text: str, color: str = INK, **kwargs):
    """Label a line at its terminal point instead of using a legend."""
    ax.annotate(text, xy=(x, y), xytext=(6, 0), textcoords="offset points",
                va="center", ha="left", color=color, fontsize=9, fontweight="medium", **kwargs)


def add_event_flags(ax, events: list[dict] | None = None, y_frac: float = 0.94, label_events: bool = True):
    """Overlay the shared event registry (config.EVENTS) as vertical spans/lines."""
    events = events if events is not None else config.EVENTS
    ymin, ymax = ax.get_ylim()
    for ev in events:
        start = _dt.date.fromisoformat(ev["date"])
        if ev.get("kind") == "span" and ev.get("end"):
            end = _dt.date.fromisoformat(ev["end"])
            ax.axvspan(start, end, color=EVENT_SPAN, alpha=0.35, lw=0, zorder=0)
            mid = start + (end - start) / 2
        else:
            ax.axvline(start, color=EVENT_SPAN, lw=1, linestyle="--", zorder=0)
            mid = start
        if label_events:
            ax.annotate(ev["label"], xy=(mid, ymin + (ymax - ymin) * y_frac), rotation=90,
                        fontsize=7, color=INK_MUTED, ha="right", va="top")
    ax.set_ylim(ymin, ymax)


def small_multiples_grid(n_panels: int, ncols: int = 3, figsize_per_panel=(3.6, 2.6), sharex=True, sharey=False):
    """Shared-axes small-multiples grid; each panel gets its own direct title (set by caller)."""
    nrows = -(-n_panels // ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(figsize_per_panel[0] * ncols, figsize_per_panel[1] * nrows),
                              sharex=sharex, sharey=sharey, facecolor=BG)
    axes_flat = axes.flatten() if n_panels > 1 else [axes]
    for ax in axes_flat[n_panels:]:
        ax.axis("off")
    return fig, axes_flat[:n_panels]


def format_date_axis(ax, interval_months: int = 6):
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=interval_months))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))


def save_figure(fig, name: str, headline: str, subtitle: str = "", source: str = "",
                 notes: str = "", out_dir: Path | None = None) -> tuple[Path, Path]:
    """Stamp the NYT-style scaffold (headline/subtitle/source/byline) onto `fig`
    and write both PNG @300dpi and SVG to figures/. Returns (png_path, svg_path).

    Header/footer bands are sized in inches, not a fixed fraction of figure
    height, so short-and-wide figures (small-multiples rows) don't get their
    panel titles crushed against the headline the way a flat top=0.80 would.
    """
    out_dir = Path(out_dir or config.FIGURES_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    fig_w, fig_h = fig.get_size_inches()
    # Rough char-per-line budget at this fontsize/figure width, so a long
    # subtitle that wraps to 2 lines gets a second line of vertical room.
    chars_per_line = max(fig_w * 11, 20)
    subtitle_lines = -(-len(subtitle) // chars_per_line) if subtitle else 0
    header_in = (0.42 + 0.28 * subtitle_lines) if subtitle else 0.55
    # Leaves room below the plot area for axis tick labels + an axis title
    # (most charts have one) before the source/byline band starts.
    footer_in = 0.85 if notes else 0.7
    top = 1 - header_in / fig_h
    bottom = footer_in / fig_h
    fig.subplots_adjust(top=top, bottom=bottom)

    fig.text(0.02, 1 - (0.28 / fig_h), headline, fontsize=15, fontweight="bold", color=INK, ha="left", va="top", wrap=True)
    if subtitle:
        fig.text(0.02, 1 - (0.55 / fig_h), subtitle, fontsize=10.5, color=INK_MUTED, ha="left", va="top", wrap=True)
    if source:
        fig.text(0.02, 0.16 / fig_h, f"SOURCE: {source.upper()}", fontsize=7.5, color=INK_MUTED, ha="left", va="bottom")
    dateline = _dt.date.today().isoformat()
    fig.text(0.98, 0.16 / fig_h, f"{BYLINE} · {dateline}", fontsize=7.5, color=INK_MUTED, ha="right", va="bottom")
    if notes:
        fig.text(0.02, 0.30 / fig_h, notes, fontsize=7, color=INK_MUTED, ha="left", va="bottom", style="italic")

    png_path = out_dir / f"{name}.png"
    svg_path = out_dir / f"{name}.svg"
    fig.savefig(png_path, dpi=300, facecolor=BG)
    fig.savefig(svg_path, facecolor=BG)
    return png_path, svg_path


# ---------------------------------------------------------------------------
# Altair theme (interactive HTML counterparts)
# ---------------------------------------------------------------------------
def altair_theme() -> dict:
    return {
        "config": {
            "background": BG,
            "view": {"stroke": "transparent"},
            "axis": {
                "domain": False,
                "gridColor": GRID,
                "gridDash": [1, 0],
                "tickColor": GRID,
                "labelColor": INK_MUTED,
                "titleColor": INK_MUTED,
                "labelFontSize": 10,
                "titleFontSize": 10,
            },
            "axisX": {"grid": False},
            "axisY": {"grid": True},
            "legend": {"labelColor": INK_MUTED, "titleColor": INK_MUTED, "labelFontSize": 10},
            "title": {"color": INK, "fontSize": 14, "fontWeight": "bold", "anchor": "start"},
            "range": {"category": [ACCENT] + WARM_GRAY, "diverging": [DIVERGING[0], WARM_GRAY[2], DIVERGING[1]]},
            "line": {"strokeWidth": 2.2},
        }
    }


def register_altair_theme():
    import altair as alt
    alt.themes.register("clo_atlas", altair_theme)
    alt.themes.enable("clo_atlas")


def main():
    apply_theme()
    fig, ax = plt.subplots(figsize=(8, 5))
    import numpy as np
    x = np.arange(100)
    ax.plot(x, np.cumsum(np.random.randn(100)), color=ACCENT)
    save_figure(fig, "style_demo", "This is a demo headline sentence.",
                subtitle="Subtitle carries the technical description.",
                source="clo-atlas demo", notes="Synthetic data, style.py self-test only.")
    print("wrote figures/style_demo.png/.svg")


if __name__ == "__main__":
    main()
