from __future__ import annotations

import os
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pg = pytest.importorskip("pyqtgraph")


def _fake_response_result():
    from cdc_analyzer.dynamic_analysis import CURRENT, LOAD, TIME, VELOCITY

    t = np.linspace(1.098, 1.142, 180)
    current = np.interp(t, [1.098, 1.109, 1.118, 1.142], [1.62, 1.62, 0.30, 0.30])
    load = np.interp(t, [1.098, 1.110, 1.118, 1.142], [-2700, -2600, -850, -900])
    velocity = np.interp(t, [1.098, 1.104, 1.115, 1.142], [-0.575, -0.495, -0.560, -0.525])
    processed = pd.DataFrame({TIME: t, CURRENT: current, LOAD: load, VELOCITY: velocity})
    events = pd.DataFrame([
        {
            "Event ID": 1,
            "Segment Start s": 1.098,
            "Segment End s": 1.142,
            "Display Start s": 1.098,
            "Display End s": 1.142,
            "t0 s": 1.1094,
            "Trigger Current A": 1.49,
            "Current 100% A": 0.31,
            "Stage": "Hard→Soft",
            "Direction": "Compression",
            "Current Transition": "1.60A→0.28A",
            "F1 N": -2630.0,
            "F63 N": -1530.0,
            "F90 N": -1010.0,
            "F100 N": -880.0,
            "Dead Time t1 ms": 0.91,
            "Switch Time t63 ms": 5.12,
            "Switch Time t90 ms": 7.03,
            "Target Velocity m/s": -0.524,
        }
    ])
    return SimpleNamespace(events=events, processed=processed, settings={})


def _plot_texts(plot):
    values = []
    for item in plot.items:
        text_item = getattr(item, "textItem", None)
        if text_item is not None:
            text = text_item.toPlainText()
            if text:
                values.append(text)
    return values


def test_v081_uses_subscripts_and_embeds_response_time_results():
    from PySide6 import QtWidgets
    from cdc_analyzer.gui_release_v081 import _build_release_gui_classes_v081

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    MainWindow = _build_release_gui_classes_v081()
    window = MainWindow()
    pages = window.dynamic_pages
    window.language = "zh_CN"

    assert pages.response_target_speeds.text() == "0.131, 0.524, 1.048"

    pages.response_result = _fake_response_result()
    pages._rebuild_response_event_combo()
    pages.refresh_response_plot()

    current_plot = pages.response_plot_area.getItem(0, 0)
    force_plot = pages.response_plot_area.getItem(1, 0)
    velocity_plot = pages.response_plot_area.getItem(2, 0)

    current_texts = _plot_texts(current_plot)
    force_texts = _plot_texts(force_plot)

    assert "I₁₀%" in current_texts
    assert "I₁₀₀%" in current_texts
    for label in ("F₁%", "F₆₃%", "F₉₀%", "F₁₀₀%"):
        assert label in force_texts
    assert "t₁% = 0.91 ms" in force_texts
    assert "t₆₃% = 5.12 ms" in force_texts
    assert "t₉₀% = 7.03 ms" in force_texts

    velocity_lines = [item for item in velocity_plot.items if isinstance(item, pg.InfiniteLine)]
    assert len(velocity_lines) == 1
    assert float(velocity_lines[0].value()) == pytest.approx(-0.524)

    window.close()
    app.processEvents()
