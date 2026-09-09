from __future__ import annotations

import sys

from . import gui_release as _base_release
from . import gui_release_v077 as _v077_module
from . import gui_release_v078 as _v078_module
from .dynamic_gui_v079 import DynamicPagesController
from .gui import _qt_imports
from .product_info import COMPANY_EN, PRODUCT_NAME

# Redirect the release-controller chain to V0.7.9. V0.7.8 ultimately builds
# through V0.7.7, so patch both module globals explicitly.
_v078_module.DynamicPagesController = DynamicPagesController
_v077_module.DynamicPagesController = DynamicPagesController

# Keep all existing help content, but simplify the page H1 as requested.
_original_release_help_html = _base_release._release_help_html


def _release_help_html_v079(language: str) -> str:
    html = _original_release_help_html(language)
    html = html.replace(
        f"{PRODUCT_NAME} — 专业帮助",
        PRODUCT_NAME,
    )
    html = html.replace(
        f"{PRODUCT_NAME} — Professional Help",
        PRODUCT_NAME,
    )
    return html


_base_release._release_help_html = _release_help_html_v079


def _build_release_gui_classes_v079():
    # Re-assert the controller just before construction so test/import order
    # cannot fall back to an older dynamic controller.
    _v078_module.DynamicPagesController = DynamicPagesController
    _v077_module.DynamicPagesController = DynamicPagesController
    _QtCore, QtWidgets, _pg = _qt_imports()
    BaseMainWindow = _v078_module._build_release_gui_classes_v078()

    class MainWindow(BaseMainWindow):
        def _show_about_dialog(self):
            QtWidgets.QMessageBox.information(
                self,
                "关于软件" if self.language == "zh_CN" else "About",
                (
                    "Damper Test Data Analyzer\n"
                    "减振器 / CDC 试验数据分析工具\n"
                    "V0.7.9"
                    if self.language == "zh_CN"
                    else "Damper Test Data Analyzer\nDamper / CDC test-data analysis\nV0.7.9"
                ),
            )

    return MainWindow


def main() -> int:
    _QtCore, QtWidgets, _pg = _qt_imports()
    MainWindow = _build_release_gui_classes_v079()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName(PRODUCT_NAME)
    app.setOrganizationName(COMPANY_EN)
    window = MainWindow()
    window.show()
    return int(app.exec())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
