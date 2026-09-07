from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")


def test_main_window_constructs_offscreen():
    from PySide6 import QtWidgets
    from cdc_analyzer.gui import _build_gui_classes

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    MainWindow = _build_gui_classes()
    window = MainWindow()
    assert "CDC Zero Position Force Analyzer" in window.windowTitle()
    window.close()
    app.processEvents()
