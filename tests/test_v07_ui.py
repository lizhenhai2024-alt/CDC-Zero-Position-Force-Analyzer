from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")


def test_v07_toolbar_help_and_response_overview_controls():
    from PySide6 import QtWidgets
    from cdc_analyzer.gui_release_v07 import RESPONSE_MARKER_BLUE, _build_release_gui_classes

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    MainWindow = _build_release_gui_classes()
    window = MainWindow()

    assert window.language == "zh_CN"
    assert window.release_language_label.text() == "语言"
    assert window.help_button.isHidden()
    assert window.tabs.tabText(window.tabs.indexOf(window.help_page)) == "帮助"
    assert "帮助" in window.help_browser.toPlainText()

    assert window.response_view_mode is not None
    assert window.response_view_mode.currentData() == "detail"
    assert window.response_view_mode.itemText(window.response_view_mode.findData("overview")) == "全流程总览（Audi图15）"

    controller = window.dynamic_pages
    assert controller.response_plot_area.minimumHeight() >= 650
    assert controller.hysteresis_plot_area.minimumHeight() >= 540
    assert controller.response_export_image_button.text() == "导出图片"
    assert controller.hysteresis_export_image_button.text() == "导出图片"

    assert window.response_zoom_in_button.text() == "放大"
    assert window.response_zoom_out_button.text() == "缩小"
    assert window.response_box_zoom_button.text() == "框选放大"
    assert window.response_pan_button.text() == "平移"
    assert window.response_reset_button.text() == "恢复"
    assert window.response_pan_button.isChecked()
    assert window._v07_response_marker_color == RESPONSE_MARKER_BLUE == "#1565C0"

    # Chinese result-table headers are active on the production V0.7 UI.
    assert controller._header("Event ID") == "事件编号"
    assert controller._header("F10 N") == "F10% / N"
    assert controller._header("Direction") == "方向"

    window.language_combo.setCurrentIndex(window.language_combo.findData("en_US"))
    app.processEvents()
    assert window.release_language_label.text() == "Language"
    assert window.help_button.isHidden()
    assert window.tabs.tabText(window.tabs.indexOf(window.help_page)) == "Help"
    assert window.response_view_mode.itemText(window.response_view_mode.findData("overview")) == "Full overview (Audi Fig. 15)"
    assert window.response_zoom_in_button.text() == "Zoom in"
    assert window.response_reset_button.text() == "Reset"

    window.close()
    app.processEvents()


def test_response_plot_reset_and_marker_segments_are_bounded():
    from PySide6 import QtWidgets
    from cdc_analyzer.gui_release_v07 import _build_release_gui_classes

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    MainWindow = _build_release_gui_classes()
    window = MainWindow()
    controller = window.dynamic_pages

    controller.response_plot_area.clear()
    first = controller.response_plot_area.addPlot(row=0, col=0)
    second = controller.response_plot_area.addPlot(row=1, col=0)
    second.setXLink(first)
    first.plot([0.0, 1.0, 2.0], [0.0, 2.0, 0.0])
    second.plot([0.0, 1.0, 2.0], [0.0, -10.0, -20.0])
    first.getViewBox().setRange(xRange=(0.0, 2.0), yRange=(-1.0, 3.0), padding=0)
    second.getViewBox().setRange(yRange=(-25.0, 5.0), padding=0)
    window._response_plots_v07 = [first, second]
    window._capture_response_ranges_v07()
    initial = first.viewRange()

    window._zoom_response_v07(0.80)
    zoomed = first.viewRange()
    assert zoomed[0][1] - zoomed[0][0] < initial[0][1] - initial[0][0]

    window._reset_response_view_v07()
    restored = first.viewRange()
    assert restored[0] == pytest.approx(initial[0], rel=1e-6, abs=1e-6)
    assert restored[1] == pytest.approx(initial[1], rel=1e-6, abs=1e-6)

    # A force-threshold vertical marker is a finite segment from the X axis (F=0)
    # to the intersection, rather than a full-height InfiniteLine.
    item = window._add_marker_segment_v07(second, 1.25, 0.0, 1.25, -18.0)
    assert list(item.xData) == pytest.approx([1.25, 1.25])
    assert list(item.yData) == pytest.approx([0.0, -18.0])

    # A horizontal marker likewise ends at the threshold intersection.
    item_h = window._add_marker_segment_v07(second, 0.40, -12.0, 1.10, -12.0)
    assert list(item_h.xData) == pytest.approx([0.40, 1.10])
    assert list(item_h.yData) == pytest.approx([-12.0, -12.0])

    window.close()
    app.processEvents()
