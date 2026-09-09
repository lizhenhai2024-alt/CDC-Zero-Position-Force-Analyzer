from __future__ import annotations

import sys
from pathlib import Path

from . import gui_release as _base_release
from .dynamic_analysis import load_dynamic_test_data
from .gui import _qt_imports
from .i18n import tr
from .product_info import COMPANY_EN, PRODUCT_NAME
from .runtime_dynamic_gui import DynamicPagesController


def _refresh_tab_controls(window) -> None:
    if getattr(window, "release_tab_language_label", None) is not None:
        window.release_tab_language_label.setText(
            "语言" if window.language == "zh_CN" else "Language"
        )
    if getattr(window, "help_button", None) is not None:
        window.help_button.setText("帮助" if window.language == "zh_CN" else "Help")


def _show_help_dialog(window, QtWidgets) -> None:
    dialog = QtWidgets.QDialog(window)
    dialog.setWindowTitle("帮助" if window.language == "zh_CN" else "Help")
    dialog.resize(980, 720)
    layout = QtWidgets.QVBoxLayout(dialog)
    browser = QtWidgets.QTextBrowser()
    browser.setOpenExternalLinks(True)
    browser.setHtml(_base_release._release_help_html(window.language))
    layout.addWidget(browser, 1)

    close_button = QtWidgets.QPushButton(
        "关闭" if window.language == "zh_CN" else "Close"
    )
    close_button.clicked.connect(dialog.accept)
    button_row = QtWidgets.QHBoxLayout()
    button_row.addStretch(1)
    button_row.addWidget(close_button)
    layout.addLayout(button_row)

    window._v075_help_dialog = dialog
    dialog.exec()


def _install_tab_language_help(window, QtCore, QtWidgets) -> None:
    """Move Language/Help onto the tab row directly after Hysteresis."""

    # Keep the legacy help page alive for the base language-update code, but do
    # not expose it as a user-facing tab.
    help_index = window.tabs.indexOf(window.help_page)
    if help_index >= 0:
        window.tabs.setTabVisible(help_index, False)

    controls = QtWidgets.QWidget()
    controls.setObjectName("releaseTabControls")
    row = QtWidgets.QHBoxLayout(controls)
    row.setContentsMargins(10, 0, 2, 0)
    row.setSpacing(6)

    label = QtWidgets.QLabel()
    label.setObjectName("releaseTabLanguageLabel")
    row.addWidget(label)

    # Re-parent the existing combo/button so all existing language state and
    # signal wiring is retained.
    window.language_combo.setParent(controls)
    window.language_combo.setMinimumWidth(108)
    window.language_combo.setMaximumWidth(145)
    window.language_combo.setMinimumHeight(26)
    row.addWidget(window.language_combo)

    try:
        window.help_button.clicked.disconnect()
    except (RuntimeError, TypeError):
        pass
    window.help_button.setParent(controls)
    window.help_button.setMinimumHeight(26)
    window.help_button.setMaximumWidth(80)
    window.help_button.clicked.connect(
        lambda: _show_help_dialog(window, QtWidgets)
    )
    row.addWidget(window.help_button)

    if getattr(window, "release_language_toolbar", None) is not None:
        window.release_language_toolbar.hide()

    hysteresis_index = window.tabs.indexOf(window.dynamic_pages.hysteresis_page)
    if hysteresis_index >= 0:
        window.tabs.tabBar().setTabButton(
            hysteresis_index,
            QtWidgets.QTabBar.ButtonPosition.RightSide,
            controls,
        )
    else:
        window.tabs.setCornerWidget(controls, QtCore.Qt.Corner.TopRightCorner)

    window.release_tab_controls = controls
    window.release_tab_language_label = label
    _refresh_tab_controls(window)
    window.language_combo.currentIndexChanged.connect(
        lambda _index: _refresh_tab_controls(window)
    )


def _build_release_gui_classes_v075():
    QtCore, QtWidgets, _pg = _qt_imports()
    _base_release.DynamicPagesController = DynamicPagesController
    BaseMainWindow = _base_release._build_release_gui_classes()

    class MainWindow(BaseMainWindow):
        def __init__(self):
            super().__init__()
            _install_tab_language_help(self, QtCore, QtWidgets)

    return MainWindow


def _build_release_gui_classes_v076():
    QtCore, QtWidgets, _pg = _qt_imports()
    from PySide6 import QtGui

    BaseMainWindow = _build_release_gui_classes_v075()

    class MainWindow(BaseMainWindow):
        def __init__(self):
            # The V0.7.5 builder has already pointed the release shell at its
            # dynamic controller. Replace that dependency before construction.
            from . import gui_release as _base_release

            _base_release.DynamicPagesController = DynamicPagesController
            super().__init__()

            # V0.7.6 replaces the tab-attached language/help controls with a
            # conventional application menu bar.
            if getattr(self, "release_tab_controls", None) is not None:
                self.release_tab_controls.hide()
            if getattr(self, "release_language_toolbar", None) is not None:
                self.release_language_toolbar.hide()
            self._build_v076_menu_bar()
            self._refresh_v076_menus()
            self.language_combo.currentIndexChanged.connect(
                lambda _index: self._refresh_v076_menus()
            )

        def _build_v076_menu_bar(self):
            menu_bar = self.menuBar()
            menu_bar.clear()
            menu_bar.setNativeMenuBar(False)

            self.file_menu = menu_bar.addMenu("")
            self.file_open_action = QtGui.QAction(self)
            self.file_open_action.triggered.connect(self.open_file)
            self.file_menu.addAction(self.file_open_action)
            self.file_menu.addSeparator()
            self.file_exit_action = QtGui.QAction(self)
            self.file_exit_action.triggered.connect(self.close)
            self.file_menu.addAction(self.file_exit_action)

            self.export_menu = menu_bar.addMenu("")
            self.export_excel_action = QtGui.QAction(self)
            self.export_excel_action.triggered.connect(self.export_excel)
            self.export_png_action = QtGui.QAction(self)
            self.export_png_action.triggered.connect(self.export_png)
            self.export_menu.addAction(self.export_excel_action)
            self.export_menu.addAction(self.export_png_action)

            self.language_menu = menu_bar.addMenu("")
            self.language_action_group = QtGui.QActionGroup(self)
            self.language_action_group.setExclusive(True)
            self.language_zh_action = QtGui.QAction("中文", self, checkable=True)
            self.language_en_action = QtGui.QAction("English", self, checkable=True)
            self.language_action_group.addAction(self.language_zh_action)
            self.language_action_group.addAction(self.language_en_action)
            self.language_menu.addAction(self.language_zh_action)
            self.language_menu.addAction(self.language_en_action)
            self.language_zh_action.triggered.connect(
                lambda: self._set_menu_language("zh_CN")
            )
            self.language_en_action.triggered.connect(
                lambda: self._set_menu_language("en_US")
            )

            self.help_menu = menu_bar.addMenu("")
            self.help_guide_action = QtGui.QAction(self)
            self.help_guide_action.triggered.connect(
                lambda: _show_help_dialog(self, QtWidgets)
            )
            self.help_about_action = QtGui.QAction(self)
            self.help_about_action.triggered.connect(self._show_about_dialog)
            self.help_menu.addAction(self.help_guide_action)
            self.help_menu.addAction(self.help_about_action)

        def _set_menu_language(self, language: str):
            index = self.language_combo.findData(language)
            if index >= 0 and index != self.language_combo.currentIndex():
                self.language_combo.setCurrentIndex(index)
            self._refresh_v076_menus()

        def _refresh_v076_menus(self):
            if not hasattr(self, "file_menu"):
                return
            zh = self.language == "zh_CN"
            self.file_menu.setTitle("文件" if zh else "File")
            self.file_open_action.setText("打开数据…" if zh else "Open Data…")
            self.file_exit_action.setText("退出" if zh else "Exit")
            self.export_menu.setTitle("导出" if zh else "Export")
            self.export_excel_action.setText("导出 Excel…" if zh else "Export Excel…")
            self.export_png_action.setText("导出 PNG…" if zh else "Export PNG…")
            self.language_menu.setTitle("语言" if zh else "Language")
            self.help_menu.setTitle("帮助" if zh else "Help")
            self.help_guide_action.setText("使用说明" if zh else "User Guide")
            self.help_about_action.setText("关于软件" if zh else "About")
            self.language_zh_action.setChecked(self.language == "zh_CN")
            self.language_en_action.setChecked(self.language == "en_US")

        def _show_about_dialog(self):
            QtWidgets.QMessageBox.information(
                self,
                "关于软件" if self.language == "zh_CN" else "About",
                (
                    "Damper Test Data Analyzer\n"
                    "减振器 / CDC 试验数据分析工具\n"
                    "V0.7.6"
                    if self.language == "zh_CN"
                    else "Damper Test Data Analyzer\nDamper / CDC test-data analysis\nV0.7.6"
                ),
            )

        def open_file(self):
            filename, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                tr(self.language, "open_test_data"),
                "",
                tr(self.language, "test_data_filter"),
            )
            if not filename:
                return
            try:
                dataset = load_dynamic_test_data(filename)
            except Exception as exc:
                QtWidgets.QMessageBox.critical(
                    self,
                    tr(self.language, "import_error"),
                    str(exc),
                )
                return

            self.dataset = dataset
            self.current_path = Path(filename)
            self._update_file_meta()
            if getattr(self, "dynamic_pages", None) is not None:
                self.dynamic_pages.set_shared_dataset(dataset, self.current_path)

            # Preserve the original left-side workflow: loading data also
            # refreshes the conventional damping-force analysis. The dynamic
            # modules wait for their own Analyze buttons because their OEM
            # parameters are independent.
            self.analyze()
            self.statusBar().showMessage(
                (
                    "数据已加载：阻尼力、响应时间和迟滞共用同一数据源"
                    if self.language == "zh_CN"
                    else "Data loaded: damping force, response time and hysteresis share one source"
                )
            )

        def _current_dynamic_module(self) -> str | None:
            pages = getattr(self, "dynamic_pages", None)
            if pages is None:
                return None
            current = self.tabs.currentWidget()
            if current is pages.response_page:
                return "response"
            if current is pages.hysteresis_page:
                return "hysteresis"
            return None

        def export_excel(self):
            module = self._current_dynamic_module()
            if module == "response":
                self.dynamic_pages.export_response()
                return
            if module == "hysteresis":
                self.dynamic_pages.export_hysteresis()
                return
            super().export_excel()

        def _export_main_png_high_resolution(self):
            if self.result is None:
                return
            default = (
                self.current_path.stem + "_plot.png"
                if self.current_path is not None
                else "plot.png"
            )
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                tr(self.language, "export_plot"),
                default,
                "PNG (*.png)",
            )
            if not filename:
                return
            try:
                import pyqtgraph.exporters

                exporter = pyqtgraph.exporters.ImageExporter(self.plot_area.scene())
                params = exporter.parameters()
                params["width"] = max(2400, int(max(self.plot_area.width(), 800) * 3.0))
                exporter.export(filename)
                self.statusBar().showMessage(
                    tr(self.language, "plot_exported").format(path=filename)
                )
            except Exception as exc:
                QtWidgets.QMessageBox.critical(
                    self,
                    tr(self.language, "export_error"),
                    str(exc),
                )

        def export_png(self):
            module = self._current_dynamic_module()
            if module == "response":
                self.dynamic_pages.export_response_png()
                return
            if module == "hysteresis":
                self.dynamic_pages.export_hysteresis_png()
                return
            self._export_main_png_high_resolution()

    return MainWindow


def _build_release_gui_classes():
    """Build canonical V0.9 shell while preserving released V0.8.4 behavior."""
    _QtCore, QtWidgets, _pg = _qt_imports()
    BaseMainWindow = _build_release_gui_classes_v076()

    class MainWindow(BaseMainWindow):
        def _show_about_dialog(self):
            QtWidgets.QMessageBox.information(
                self,
                "关于软件" if self.language == "zh_CN" else "About",
                (
                    "Damper Test Data Analyzer\n"
                    "减振器 / CDC 试验数据分析工具\n"
                    "V0.8.4"
                    if self.language == "zh_CN"
                    else "Damper Test Data Analyzer\nDamper / CDC test-data analysis\nV0.8.4"
                ),
            )

    return MainWindow


def main() -> int:
    _QtCore, QtWidgets, _pg = _qt_imports()
    MainWindow = _build_release_gui_classes()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName(PRODUCT_NAME)
    app.setOrganizationName(COMPANY_EN)
    window = MainWindow()
    window.show()
    return int(app.exec())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
