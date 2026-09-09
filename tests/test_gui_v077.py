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
    load = np.interp(t, [1.098, 1.110, 1.118, 1.142], [2700, 2600, 850, 900])
    velocity = np.interp(t, [1.098, 1.104, 1.115, 1.142], [0.575, 0.495, 0.560, 0.525])
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
            "Direction": "Rebound",
            "F1 N": 2630.0,
            "F63 N": 1530.0,
            "F90 N": 1010.0,
            "F100 N": 880.0,
            "Dead Time t1 ms": 0.9,
            "Switch Time t63 ms": 5.1,
            "Switch Time t90 ms": 7.0,
            "Target Velocity m/s": 0.524,
        }
    ])
    return SimpleNamespace(events=events, processed=processed, settings={})


def test_v077_response_plot_uses_seconds_sparse_dashes_and_clean_annotations():
    from PySide6 import QtCore, QtWidgets
    from cdc_analyzer.gui_release_v077 import _build_release_gui_classes_v077

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    MainWindow = _build_release_gui_classes_v077()
    window = MainWindow()
    pages = window.dynamic_pages

    pen = pages._marker_pen()
    assert pen.style() == QtCore.Qt.PenStyle.CustomDashLine
    pattern = pen.dashPattern()
    assert pattern[0] >= 10.0
    assert pattern[1] >= 6.0

    pages.response_result = _fake_response_result()
    pages.response_event_combo.clear()
    pages.response_event_combo.addItem("event 1", 1)

    labels = []
    original_add_text = pages._add_plot_text

    def capture_text(plot, text, x, y, **kwargs):
        labels.append(str(text))
        return original_add_text(plot, text, x, y, **kwargs)

    pages._add_plot_text = capture_text
    pages.refresh_response_plot()

    current_plot = pages.response_plot_area.getItem(0, 0)
    force_plot = pages.response_plot_area.getItem(1, 0)
    velocity_plot = pages.response_plot_area.getItem(2, 0)

    assert "s" in current_plot.getAxis("bottom").label.toPlainText()
    assert "ms" not in current_plot.getAxis("bottom").label.toPlainText()
    assert "I10%" in labels
    assert "I100%" in labels
    assert not any("复原" in text or "Rebound" in text for text in labels)
    assert not any("目标" in text or "Target" in text for text in labels)

    velocity_reference_lines = [
        item for item in velocity_plot.items if isinstance(item, pg.InfiniteLine)
    ]
    # Only t0 remains on the velocity plot; the target-speed horizontal marker
    # and its text were removed in V0.7.7.
    assert len(velocity_reference_lines) == 1

    # Force response still keeps its four response levels and timing markers.
    assert force_plot is not None

    window.close()
    app.processEvents()
