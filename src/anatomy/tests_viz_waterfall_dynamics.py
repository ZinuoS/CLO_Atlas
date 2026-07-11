"""Geometric-stability invariant for the click-through frame sequences:
renders two frames built from deliberately different scenario/period data
and asserts every static element (figure size, axes rect/limits, node box
pixel positions) is identical — only fill colors and text content may
differ. This is the enforcement mechanism the brief requires before any
`viz_waterfall_dynamics` frame sequence can be trusted to "play" cleanly
as a PowerPoint click-through.
"""
from __future__ import annotations

import numpy as np
import pytest

from src.anatomy.deal import load_deal
from src.anatomy.scenarios import build_scenarios, run_scenario
from src.anatomy.viz_waterfall_dynamics import (
    CURE_BOX, NODE_H, NODE_W, NODE_X0, NODES, render_frame,
)


def _two_frames():
    """Two frames chosen to be maximally different in content (a mid-shock
    breach quarter vs. a calm base-case quarter) so a geometry test that
    passes here isn't passing by accident."""
    deal = load_deal()
    scenarios = build_scenarios(deal)
    df_covid = run_scenario(deal, scenarios["covid_shock"])
    df_base = run_scenario(deal, scenarios["base"])
    mid_period = df_covid["period"].iloc[len(df_covid) // 2]
    row_a = df_covid[df_covid["period"] == mid_period].iloc[0]
    row_b = df_base.iloc[0]
    fig_a = render_frame(deal, scenarios["covid_shock"], row_a, step_idx=2, n_steps=5)
    fig_b = render_frame(deal, scenarios["base"], row_b, step_idx=1, n_steps=3)
    return fig_a, fig_b


def test_frames_share_identical_figure_and_axes_geometry():
    fig_a, fig_b = _two_frames()
    try:
        assert fig_a.get_size_inches() == pytest.approx(fig_b.get_size_inches())
        assert fig_a.dpi == fig_b.dpi
        ax_a, ax_b = fig_a.axes[0], fig_b.axes[0]
        assert tuple(ax_a.get_position().bounds) == pytest.approx(tuple(ax_b.get_position().bounds))
        assert ax_a.get_xlim() == pytest.approx(ax_b.get_xlim())
        assert ax_a.get_ylim() == pytest.approx(ax_b.get_ylim())
    finally:
        import matplotlib.pyplot as plt
        plt.close(fig_a)
        plt.close(fig_b)


def test_every_node_box_is_at_the_identical_pixel_position_across_frames():
    fig_a, fig_b = _two_frames()
    try:
        ax_a, ax_b = fig_a.axes[0], fig_b.axes[0]
        for key, _label, y, _level in NODES:
            for x in (NODE_X0, NODE_X0 + NODE_W):
                p_a = ax_a.transData.transform((x, y))
                p_b = ax_b.transData.transform((x, y))
                assert p_a == pytest.approx(p_b, abs=1e-6), f"node {key!r} corner ({x},{y}) shifted between frames"
        for x in (CURE_BOX["x"], CURE_BOX["x"] + CURE_BOX["w"]):
            p_a = ax_a.transData.transform((x, CURE_BOX["y"]))
            p_b = ax_b.transData.transform((x, CURE_BOX["y"]))
            assert p_a == pytest.approx(p_b, abs=1e-6), "cure box shifted between frames"
    finally:
        import matplotlib.pyplot as plt
        plt.close(fig_a)
        plt.close(fig_b)


def test_rasterized_box_border_pixels_match_outside_the_dynamic_fill_and_text():
    """Belt-and-suspenders: actually rasterize both frames and diff the exact
    pixel row along the top border of a node box that never changes fill
    color both frames chose here (senior_expenses, always neutral) — this
    proves the static structure isn't just numerically aligned but visually
    identical pixel-for-pixel where nothing data-driven should touch it."""
    import matplotlib.pyplot as plt

    fig_a, fig_b = _two_frames()
    try:
        ax = fig_a.axes[0]
        top_y = [y for key, _l, y, _lv in NODES if key == "senior_expenses"][0] + NODE_H / 2
        px, py = ax.transData.transform((NODE_X0 + NODE_W / 2, top_y))
        fig_a.canvas.draw()
        fig_b.canvas.draw()
        arr_a = np.asarray(fig_a.canvas.buffer_rgba())
        arr_b = np.asarray(fig_b.canvas.buffer_rgba())
        assert arr_a.shape == arr_b.shape
        row_px = int(round(arr_a.shape[0] - py))  # canvas y is top-down; transData y is bottom-up
        col_px = int(round(px))
        window_a = arr_a[max(0, row_px - 2):row_px + 3, max(0, col_px - 20):col_px + 20]
        window_b = arr_b[max(0, row_px - 2):row_px + 3, max(0, col_px - 20):col_px + 20]
        assert np.array_equal(window_a, window_b), "the senior_expenses box border pixels differ between frames"
    finally:
        plt.close(fig_a)
        plt.close(fig_b)


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
