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

    t = np.linspace(1.098, 1.150, 220)
    current = np.interp(t, [1.098, 1.109, 1.118, 1.150], [1.62, 1.62, 0.30, 0.30])
    load = np.interp(t, [1.098, 1.110, 1.135, 1.150], [-2700, -2600, -1200, -880])
    velocity = np.full_like(t, -0.524)
    processed = pd.DataFrame({TIME: t, CURRENT: current, LOAD: load, VELOCITY: velocity})
    events = pd.DataFrame([
        {
            "Event ID": 1,
            "Segment Start s": 1.098,
            "Segment End s": 1.150,
            "Display Start s": 1.098,
            "Display End s": 1.135,
            "Target Window End s": 1.150,
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
            "Switch Time t63 ms": 24.00,
            "Switch Time t90 ms": 36.00,
            "Target Velocity m/s": -0.524,
        }
    ])
    return SimpleNamespace(events=events, processed=processed, settings={})


def _text_items(plot):
    return [item for item in plot.items if getattr(item, "textItem", None) is not None]


def test_v083_response_labels_are_large_clear_and_cover_force_crossings():
    from PySide6 import QtWidgets
    from cdc_analyzer.gui_release_v083 import _build_release_gui_classes_v083

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    MainWindow = _build_release_gui_classes_v083()
    window = MainWindow()
    pages = window.dynamic_pages
    pages.response_result = _fake_response_result()
    pages._rebuild_response_event_combo()
    pages.refresh_response_plot()

    current_plot = pages.response_plot_area.getItem(0, 0)
    force_plot = pages.response_plot_area.getItem(1, 0)
    current_text = {item.textItem.toPlainText(): item for item in _text_items(current_plot)}
    force_text = {item.textItem.toPlainText(): item for item in _text_items(force_plot)}

    for label in ("I₁₀%", "I₁₀₀%"):
        assert current_text[label].textItem.font().pointSize() >= 12
        assert current_text[label].anchor.y() >= 1.0
    for label in ("F₁%", "F₆₃%", "F₉₀%", "F₁₀₀%"):
        assert force_text[label].textItem.font().pointSize() >= 12
        assert force_text[label].anchor.y() >= 1.0

    markers = {
        "t₁% = 0.91 ms": 1.1094 + 0.00091,
        "t₆₃% = 24.00 ms": 1.1094 + 0.024,
        "t₉₀% = 36.00 ms": 1.1094 + 0.036,
    }
    for label, marker_x in markers.items():
        item = force_text[label]
        assert item.textItem.font().pointSize() >= 12
        assert item.pos().x() != pytest.approx(marker_x)

    force_curves = [item for item in force_plot.items if isinstance(item, pg.PlotDataItem)]
    assert len(force_curves) == 1
    x, y = force_curves[0].getData()
    assert float(np.nanmax(x)) == pytest.approx(1.150)
    for level in (-2.630, -1.530, -1.010, -0.880):
        assert np.any((y[:-1] - level) * (y[1:] - level) <= 0)

    assert pages.response_limit_label.text() == "t₉₀%限值"
    help_text = window.help_browser.toPlainText()
    assert "0.1、0.3、0.6、1.0 m/s" in help_text
    assert "t₉₀%" in help_text
    assert "I₁₀%" in help_text

    window.language_combo.setCurrentIndex(window.language_combo.findData("en_US"))
    app.processEvents()
    assert pages.response_limit_label.text() == "t₉₀% limit"
    window.close()
    app.processEvents()


def test_v083_release_module_remains_available():
    from cdc_analyzer.gui_release_v083 import _build_release_gui_classes_v083

    assert callable(_build_release_gui_classes_v083)
