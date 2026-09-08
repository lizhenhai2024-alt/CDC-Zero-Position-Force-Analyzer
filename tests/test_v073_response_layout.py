from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")


def test_v073_response_layout_allows_third_plot_to_fit():
    from PySide6 import QtWidgets
    from cdc_analyzer.gui_release_v073 import (
        RESPONSE_PLOT_AREA_MIN_HEIGHT,
        RESPONSE_TABLE_MAX_HEIGHT,
        _build_release_gui_classes,
    )

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    MainWindow = _build_release_gui_classes()
    window = MainWindow()
    controller = window.dynamic_pages

    assert controller.response_plot_area.minimumHeight() == RESPONSE_PLOT_AREA_MIN_HEIGHT
    assert controller.response_table.maximumHeight() == RESPONSE_TABLE_MAX_HEIGHT

    controller.response_plot_area.clear()
    plots = []
    for row in range(3):
        plot = controller.response_plot_area.addPlot(row=row, col=0)
        plot.setMinimumHeight(235)
        plots.append(plot)
    window._response_plots_v07 = plots

    window._fit_response_plots_v073()

    assert all(plot.minimumHeight() == 0 for plot in plots)
    bottom_axis = plots[-1].getAxis("bottom")
    assert bottom_axis.isVisible()
    assert bottom_axis.label.isVisible()
    assert "时间" in bottom_axis.label.toPlainText() or "Time" in bottom_axis.label.toPlainText()

    window.close()
    app.processEvents()
