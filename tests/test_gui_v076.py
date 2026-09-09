from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")


def _dataset():
    from cdc_analyzer.dynamic_analysis import CURRENT, DISP, LOAD, TIME
    from cdc_analyzer.parser import DataSet

    frame = pd.DataFrame(
        {
            TIME: [0.0, 0.01, 0.02, 0.03, 0.04],
            DISP: [-1.0, 0.0, 1.0, 0.0, -1.0],
            LOAD: [-100.0, 100.0, 150.0, -100.0, -150.0],
            CURRENT: [0.3, 0.3, 0.3, 0.3, 0.3],
            "Block ID": [1, 1, 1, 1, 1],
        }
    )
    return DataSet(frame, Path("shared.dat"), "synthetic", {"block_count": 1})


def test_v076_uses_menu_bar_and_hides_duplicate_dynamic_actions():
    from PySide6 import QtWidgets
    from cdc_analyzer.gui_release_v076 import _build_release_gui_classes_v076

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    MainWindow = _build_release_gui_classes_v076()
    window = MainWindow()
    pages = window.dynamic_pages

    assert window.file_menu.title() == "文件"
    assert window.export_menu.title() == "导出"
    assert window.language_menu.title() == "语言"
    assert window.help_menu.title() == "帮助"
    assert window.release_language_toolbar.isHidden()
    assert window.release_tab_controls.isHidden()
    assert pages.response_open_button.isHidden()
    assert pages.response_export_button.isHidden()
    assert pages.hysteresis_open_button.isHidden()
    assert pages.hysteresis_export_button.isHidden()

    window.language_en_action.trigger()
    app.processEvents()
    assert window.language == "en_US"
    assert window.file_menu.title() == "File"
    assert window.export_menu.title() == "Export"
    assert window.language_menu.title() == "Language"
    assert window.help_menu.title() == "Help"

    window.close()
    app.processEvents()


def test_v076_shared_dataset_feeds_response_and_hysteresis():
    from PySide6 import QtWidgets
    from cdc_analyzer.gui_release_v076 import _build_release_gui_classes_v076

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    MainWindow = _build_release_gui_classes_v076()
    window = MainWindow()
    pages = window.dynamic_pages
    dataset = _dataset()

    pages.set_shared_dataset(dataset, dataset.source_path)

    assert pages.response_dataset is dataset
    assert pages.hysteresis_dataset is dataset
    assert pages.response_path == dataset.source_path
    assert pages.hysteresis_path == dataset.source_path
    assert "公共数据源" in pages.response_file_label.text()
    assert "公共数据源" in pages.hysteresis_file_label.text()

    window.close()
    app.processEvents()


def test_v076_left_export_buttons_route_by_active_module(monkeypatch):
    from PySide6 import QtWidgets
    from cdc_analyzer.gui_release_v076 import _build_release_gui_classes_v076

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    MainWindow = _build_release_gui_classes_v076()
    window = MainWindow()
    pages = window.dynamic_pages
    calls: list[str] = []

    monkeypatch.setattr(pages, "export_response", lambda: calls.append("response_xlsx"))
    monkeypatch.setattr(pages, "export_hysteresis", lambda: calls.append("hysteresis_xlsx"))
    monkeypatch.setattr(pages, "export_response_png", lambda: calls.append("response_png"))
    monkeypatch.setattr(pages, "export_hysteresis_png", lambda: calls.append("hysteresis_png"))

    window.tabs.setCurrentWidget(pages.response_page)
    window.export_excel()
    window.export_png()
    window.tabs.setCurrentWidget(pages.hysteresis_page)
    window.export_excel()
    window.export_png()

    assert calls == [
        "response_xlsx",
        "response_png",
        "hysteresis_xlsx",
        "hysteresis_png",
    ]

    window.close()
    app.processEvents()


def test_v076_left_open_data_is_shared_with_dynamic_pages(monkeypatch):
    from PySide6 import QtWidgets
    import cdc_analyzer.gui_release_v076 as release

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    MainWindow = release._build_release_gui_classes_v076()
    window = MainWindow()
    dataset = _dataset()

    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *args, **kwargs: (str(dataset.source_path), "")),
    )
    monkeypatch.setattr(release, "load_dynamic_test_data", lambda _path: dataset)
    monkeypatch.setattr(window, "analyze", lambda: None)

    window.open_file()

    assert window.dataset is dataset
    assert window.current_path == dataset.source_path
    assert window.dynamic_pages.response_dataset is dataset
    assert window.dynamic_pages.hysteresis_dataset is dataset

    window.close()
    app.processEvents()
