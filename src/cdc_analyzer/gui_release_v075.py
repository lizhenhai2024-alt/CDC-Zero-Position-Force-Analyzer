from __future__ import annotations

import sys

from . import gui_release as _base_release
from .dynamic_gui_v075 import DynamicPagesController
from .gui import _qt_imports
from .product_info import COMPANY_EN, PRODUCT_NAME


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


def main() -> int:
    _QtCore, QtWidgets, _pg = _qt_imports()
    MainWindow = _build_release_gui_classes_v075()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName(PRODUCT_NAME)
    app.setOrganizationName(COMPANY_EN)
    window = MainWindow()
    window.show()
    return int(app.exec())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
