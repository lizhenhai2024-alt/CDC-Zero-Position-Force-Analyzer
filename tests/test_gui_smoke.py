from __future__ import annotations

import os
from math import pi
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")


def _dataset():
    from cdc_analyzer.parser import DataSet

    theta = np.linspace(0, 2 * pi, 401)
    t = theta / (2 * pi) * 4.0
    x = 50.0 * np.cos(theta)
    direction = np.sign(-np.sin(theta))
    force = np.where(direction >= 0, 1000.0 + 2.0 * x, -600.0 + x)
    frame = pd.DataFrame({
        "Running Time": t,
        "Axial Displacement": x,
        "Axial Load": force,
        "CDC 1 Current FB_1": 0.8 + 0.0002 * np.sin(theta),
        "Empty Sensor": np.nan,
        "Block ID": 1,
        "Source Row": np.arange(1, len(theta) + 1),
    })
    return DataSet(frame, Path("synthetic.dat"), "synthetic")


def test_main_window_constructs_analyzes_and_switches_language_offscreen():
    from PySide6 import QtCore, QtWidgets
    from cdc_analyzer.gui_v04 import _build_gui_classes_v04

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    MainWindow = _build_gui_classes_v04()
    window = MainWindow()

    # Chinese is the required startup default.
    assert window.language == "zh_CN"
    assert window.language_combo.currentData() == "zh_CN"
    assert "零位阻尼力分析器" in window.windowTitle()
    assert window.open_button.text().startswith("打开")
    assert window.tabs.tabText(window.tabs.indexOf(window.quality_table)) == "数据质量"

    window.dataset = _dataset()
    window.analyze()

    assert "v0.5" in window.windowTitle()
    assert window.result is not None
    assert len(window.result.runs) == 1
    assert window.summary_table.model().rowCount() == 1
    assert window.quality_status == "OK"
    assert window.quality_table.model().rowCount() == 1
    # A single isolated current run has no sweep direction and is correctly excluded.
    assert window.sweep_table.model().rowCount() == 0
    assert window.x_axis.currentData() == "Running Time"
    assert window.x_axis.currentText() == "运行时间"
    expected_channels = [
        "Running Time",
        "Axial Displacement",
        "Axial Load",
        "CDC 1 Current FB_1",
    ]
    assert [window.x_axis.itemData(index) for index in range(window.x_axis.count())] == expected_channels
    assert [
        window.y_axis.item(index).data(QtCore.Qt.ItemDataRole.UserRole)
        for index in range(window.y_axis.count())
    ] == expected_channels
    selected = {
        item.data(QtCore.Qt.ItemDataRole.UserRole): item.text()
        for item in window.y_axis.selectedItems()
    }
    assert selected == {
        "Axial Displacement": "轴向位移",
        "Axial Load": "轴向载荷",
        "CDC 1 Current FB_1": "CDC 1 反馈电流",
    }
    import pyqtgraph as pg
    selected_items = window.y_axis.selectedItems()
    for index, item in enumerate(selected_items):
        assert item.foreground().color() == pg.intColor(index, hues=len(selected_items))
    window.x_axis.setCurrentIndex(window.x_axis.findData("Axial Displacement"))
    for index in range(window.y_axis.count()):
        item = window.y_axis.item(index)
        item.setSelected(item.data(QtCore.Qt.ItemDataRole.UserRole) == "Axial Load")
    window.analyze()
    assert window.x_axis.currentData() == "Axial Displacement"
    assert [item.data(QtCore.Qt.ItemDataRole.UserRole) for item in window.y_axis.selectedItems()] == ["Axial Load"]

    # A newly imported dataset reapplies the first-column/all-other-columns defaults.
    window.dataset = _dataset()
    window.analyze()
    assert window.x_axis.currentData() == "Running Time"
    assert {item.data(QtCore.Qt.ItemDataRole.UserRole) for item in window.y_axis.selectedItems()} == {
        "Axial Displacement", "Axial Load", "CDC 1 Current FB_1"
    }
    assert window.summary_table.model().headerData(
        0, QtCore.Qt.Orientation.Horizontal, QtCore.Qt.ItemDataRole.DisplayRole
    ) == "电流档位 A"

    # Switching language must change display text only, not analysis/data keys.
    window.language_combo.setCurrentIndex(window.language_combo.findData("en_US"))
    app.processEvents()
    assert window.language == "en_US"
    assert window.windowTitle() == "CDC Zero Position Force Analyzer v0.5"
    assert window.x_axis.currentData() == "Running Time"
    assert window.x_axis.currentText() == "Running Time"
    assert window.tabs.tabText(window.tabs.indexOf(window.sweep_table)) == "Sweep Comparison"
    assert window.summary_table.model().headerData(
        0, QtCore.Qt.Orientation.Horizontal, QtCore.Qt.ItemDataRole.DisplayRole
    ) == "Current Label A"

    window.close()
    app.processEvents()


def test_invalid_time_axis_is_blocked_before_engineering_analysis(monkeypatch):
    from PySide6 import QtWidgets
    from cdc_analyzer.gui_v04 import _build_gui_classes_v04

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    MainWindow = _build_gui_classes_v04()
    window = MainWindow()
    dataset = _dataset()
    dataset.data.loc[50, "Running Time"] = dataset.data.loc[49, "Running Time"]
    window.dataset = dataset

    messages: list[str] = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "critical",
        lambda *args: messages.append(str(args[-1])) or QtWidgets.QMessageBox.StandardButton.Ok,
    )
    window.analyze()

    assert window.result is None
    assert window.quality_status == "Invalid"
    assert window.quality_table.model().rowCount() == 1
    assert "non-increasing time" in str(window.quality_frame.iloc[0]["Issues"])
    assert messages
    assert "原始数据预检" in messages[0]

    window.close()
    app.processEvents()
