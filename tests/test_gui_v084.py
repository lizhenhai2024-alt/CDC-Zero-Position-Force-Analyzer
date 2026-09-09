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


def _scatter_points(plot):
    points = []
    for item in plot.items:
        if isinstance(item, pg.ScatterPlotItem):
            x, y = item.getData()
            points.extend((float(px), float(py)) for px, py in zip(x, y))
    return points


def _assert_transparent_normal_axis_font(plot, item, QtCore):
    axis_font = plot.getAxis("left").label.font()
    font = item.textItem.font()
    assert font.pointSize() == axis_font.pointSize()
    assert font.pixelSize() == axis_font.pixelSize()
    assert not font.bold()
    fill = getattr(item, "fill", None)
    if fill is not None and hasattr(fill, "style"):
        assert fill.style() == QtCore.Qt.BrushStyle.NoBrush


def test_v084_response_annotations_match_axis_font_and_are_transparent():
    from PySide6 import QtCore, QtWidgets
    from cdc_analyzer.gui_release_v084 import _build_release_gui_classes_v084

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    MainWindow = _build_release_gui_classes_v084()
    window = MainWindow()
    pages = window.dynamic_pages
    pages.response_result = _fake_response_result()
    pages._rebuild_response_event_combo()
    pages.refresh_response_plot()

    current_plot = pages.response_plot_area.getItem(0, 0)
    force_plot = pages.response_plot_area.getItem(1, 0)
    current_text = {item.textItem.toPlainText(): item for item in _text_items(current_plot)}
    force_text = {item.textItem.toPlainText(): item for item in _text_items(force_plot)}

    for label in ("I₁₀%", "I₁₀₀%", "t₀"):
        _assert_transparent_normal_axis_font(current_plot, current_text[label], QtCore)
    for label in (
        "F₁%",
        "F₆₃%",
        "F₉₀%",
        "F₁₀₀%",
        "t₀",
        "t₁% = 0.91 ms",
        "t₆₃% = 24.00 ms",
        "t₉₀% = 36.00 ms",
    ):
        _assert_transparent_normal_axis_font(force_plot, force_text[label], QtCore)

    window.close()
    app.processEvents()


def test_v084_vertical_lines_have_curve_intersection_dots_and_aligned_text():
    from PySide6 import QtWidgets
    from cdc_analyzer.gui_release_v084 import _build_release_gui_classes_v084

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    MainWindow = _build_release_gui_classes_v084()
    window = MainWindow()
    pages = window.dynamic_pages
    result = _fake_response_result()
    pages.response_result = result
    pages._rebuild_response_event_combo()
    pages.refresh_response_plot()

    current_plot = pages.response_plot_area.getItem(0, 0)
    force_plot = pages.response_plot_area.getItem(1, 0)
    current_text = {item.textItem.toPlainText(): item for item in _text_items(current_plot)}
    force_text = {item.textItem.toPlainText(): item for item in _text_items(force_plot)}

    t0 = 1.1094
    marker_times = {
        "t₀": t0,
        "t₁% = 0.91 ms": t0 + 0.00091,
        "t₆₃% = 24.00 ms": t0 + 0.024,
        "t₉₀% = 36.00 ms": t0 + 0.036,
    }

    current_points = _scatter_points(current_plot)
    assert len(current_points) == 1
    assert current_points[0][0] == pytest.approx(t0)
    expected_current_y = np.interp(t0, result.processed["Running Time"], result.processed["CDC 1 Current FB_1"])
    assert current_points[0][1] == pytest.approx(expected_current_y)
    assert current_text["t₀"].pos().x() == pytest.approx(t0)
    assert current_text["t₀"].pos().y() != pytest.approx(current_points[0][1])

    force_points = sorted(_scatter_points(force_plot), key=lambda point: point[0])
    assert len(force_points) == 4
    force_time = result.processed["Running Time"].to_numpy(float)
    force_kn = result.processed["Axial Load"].to_numpy(float) / 1000.0
    for label, expected_x in marker_times.items():
        point = min(force_points, key=lambda p: abs(p[0] - expected_x))
        assert point[0] == pytest.approx(expected_x)
        assert point[1] == pytest.approx(np.interp(expected_x, force_time, force_kn))
        assert force_text[label].pos().x() == pytest.approx(expected_x)
        assert force_text[label].pos().y() != pytest.approx(point[1])

    window.close()
    app.processEvents()


def test_v084_is_the_packaged_gui_entry_point():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    assert "gui_release_v084" in (root / "launcher.py").read_text(encoding="utf-8")
    assert 'cdc_analyzer.gui_release_v084:main' in (root / "pyproject.toml").read_text(encoding="utf-8")
