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
            "Dead Time t1 ms": 0.9,
            "Switch Time t63 ms": 5.1,
            "Switch Time t90 ms": 7.0,
            "Target Velocity m/s": -0.524,
        }
    ])
    return SimpleNamespace(events=events, processed=processed, settings={})


def test_v078_chinese_localization_and_velocity_target_line():
    from PySide6 import QtWidgets
    from cdc_analyzer.gui_release_v078 import _build_release_gui_classes_v078

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    MainWindow = _build_release_gui_classes_v078()
    window = MainWindow()
    pages = window.dynamic_pages
    window.language = "zh_CN"

    pages.response_result = _fake_response_result()
    pages._rebuild_response_event_combo()
    pages._fill_table(pages.response_table, pages.response_result.events)
    pages.refresh_response_plot()

    combo_text = pages.response_event_combo.currentText()
    assert "硬→软" in combo_text
    assert "压缩(-)" in combo_text
    assert "Hard" not in combo_text
    assert "Compression" not in combo_text

    current_plot = pages.response_plot_area.getItem(0, 0)
    title_text = current_plot.titleLabel.text
    assert "硬→软" in title_text
    assert "压缩" in title_text
    assert "Hard" not in title_text
    assert "Compression" not in title_text

    stage_col = list(pages.response_result.events.columns).index("Stage")
    direction_col = list(pages.response_result.events.columns).index("Direction")
    assert pages.response_table.item(0, stage_col).text() == "硬→软"
    assert pages.response_table.item(0, direction_col).text() == "压缩"

    velocity_plot = pages.response_plot_area.getItem(2, 0)
    reference_lines = [
        item for item in velocity_plot.items if isinstance(item, pg.InfiniteLine)
    ]
    assert len(reference_lines) == 1
    line = reference_lines[0]
    assert float(line.value()) == pytest.approx(-0.524)
    assert float(line.angle) % 180 == pytest.approx(0.0)

    window.close()
    app.processEvents()
