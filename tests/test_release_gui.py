from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")


def test_release_ui_defaults_to_chinese_and_has_professional_tools():
    from PySide6 import QtWidgets
    from cdc_analyzer.gui_release import _build_release_gui_classes
    from cdc_analyzer.product_info import COMPANY_EN, COMPANY_ZH, PRODUCT_NAME

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    MainWindow = _build_release_gui_classes()
    window = MainWindow()

    assert window.windowTitle() == PRODUCT_NAME
    assert window.language == "zh_CN"
    assert window.language_combo.currentData() == "zh_CN"
    assert window.help_button.text() == "帮助 / 使用说明"
    assert window.tabs.tabText(window.tabs.indexOf(window.help_page)) == "专业帮助"
    assert "Audi" in window.help_browser.toPlainText()
    assert "总行程 10%" in window.help_browser.toPlainText()
    assert COMPANY_ZH in window.help_browser.toPlainText()
    assert COMPANY_EN in window.help_browser.toPlainText()

    assert window.background_combo.currentData() == "white"
    assert window.zoom_in_button.text() == "放大"
    assert window.zoom_out_button.text() == "缩小"
    assert window.box_zoom_button.text() == "框选放大"
    assert window.pan_button.text() == "平移"
    assert window.reset_view_button.text() == "恢复"

    assert window.brand_title.text() == PRODUCT_NAME
    assert COMPANY_ZH in window.brand_company.text()

    window.language_combo.setCurrentIndex(window.language_combo.findData("en_US"))
    app.processEvents()
    assert window.windowTitle() == PRODUCT_NAME
    assert window.help_button.text() == "Help / User Guide"
    assert window.tabs.tabText(window.tabs.indexOf(window.help_page)) == "Professional Help"
    assert window.background_combo.itemText(window.background_combo.findData("black")) == "Black"

    window.close()
    app.processEvents()
