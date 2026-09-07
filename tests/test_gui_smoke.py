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
        "Block ID": 1,
        "Source Row": np.arange(1, len(theta) + 1),
    })
    return DataSet(frame, Path("synthetic.dat"), "synthetic")


def test_main_window_constructs_and_analyzes_offscreen():
    from PySide6 import QtWidgets
    from cdc_analyzer.gui_v04 import _build_gui_classes_v04

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    MainWindow = _build_gui_classes_v04()
    window = MainWindow()
    window.dataset = _dataset()
    window.analyze()

    assert "v0.4" in window.windowTitle()
    assert window.result is not None
    assert len(window.result.runs) == 1
    assert window.summary_table.model().rowCount() == 1
    assert window.quality_status == "OK"
    assert window.quality_table.model().rowCount() == 1
    assert window.x_axis.currentText() == "Axial Displacement"
    assert window.y_axis.selectedItems()[0].text() == "Axial Load"

    window.close()
    app.processEvents()
