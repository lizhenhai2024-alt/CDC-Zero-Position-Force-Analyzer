from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")


def test_v075_response_plot_and_table_are_separate_views():
    from PySide6 import QtWidgets
    from cdc_analyzer.gui_release_v075 import _build_release_gui_classes_v075

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    MainWindow = _build_release_gui_classes_v075()
    window = MainWindow()
    pages = window.dynamic_pages

    assert pages.response_view_tabs.count() == 2
    assert pages.response_view_tabs.tabText(0) == "图形分析"
    assert pages.response_view_tabs.tabText(1) == "结果数据"
    assert pages.response_plot_area.parentWidget() is pages.response_graph_page
    assert pages.response_table.parentWidget() is pages.response_data_page
    assert pages.response_show_plot_button.text() == "查看图形"

    pages.response_view_tabs.setCurrentWidget(pages.response_data_page)
    pages._show_selected_response_plot()
    assert pages.response_view_tabs.currentWidget() is pages.response_graph_page

    window.close()
    app.processEvents()


def test_v075_language_and_help_are_attached_beside_hysteresis_tab():
    from PySide6 import QtWidgets
    from cdc_analyzer.gui_release_v075 import _build_release_gui_classes_v075

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    MainWindow = _build_release_gui_classes_v075()
    window = MainWindow()

    help_index = window.tabs.indexOf(window.help_page)
    assert help_index >= 0
    assert not window.tabs.isTabVisible(help_index)
    assert window.release_language_toolbar.isHidden()
    assert window.release_tab_language_label.text() == "语言"
    assert window.help_button.text() == "帮助"

    hysteresis_index = window.tabs.indexOf(window.dynamic_pages.hysteresis_page)
    tab_button = window.tabs.tabBar().tabButton(
        hysteresis_index,
        QtWidgets.QTabBar.ButtonPosition.RightSide,
    )
    assert tab_button is window.release_tab_controls

    window.language_combo.setCurrentIndex(window.language_combo.findData("en_US"))
    app.processEvents()
    assert window.release_tab_language_label.text() == "Language"
    assert window.help_button.text() == "Help"
    assert pages_tab_text(window.dynamic_pages) == ("Plot Analysis", "Result Data")

    window.close()
    app.processEvents()


def pages_tab_text(pages):
    return (
        pages.response_view_tabs.tabText(
            pages.response_view_tabs.indexOf(pages.response_graph_page)
        ),
        pages.response_view_tabs.tabText(
            pages.response_view_tabs.indexOf(pages.response_data_page)
        ),
    )
