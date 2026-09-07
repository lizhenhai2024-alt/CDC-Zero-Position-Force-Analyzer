from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")


def test_v07_toolbar_help_and_response_overview_controls():
    from PySide6 import QtWidgets
    from cdc_analyzer.gui_release_v07 import _build_release_gui_classes

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

    window.close()
    app.processEvents()
