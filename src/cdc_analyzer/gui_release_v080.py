from __future__ import annotations

import sys

from . import gui_release_v079 as _v079_module
from .dynamic_gui_v080 import DynamicPagesController
from .gui import _qt_imports
from .product_info import COMPANY_EN, PRODUCT_NAME

_v079_module.DynamicPagesController = DynamicPagesController


def _build_release_gui_classes_v080():
    _QtCore, QtWidgets, _pg = _qt_imports()
    BaseMainWindow = _v079_module._build_release_gui_classes_v079()

    class MainWindow(BaseMainWindow):
        def _show_about_dialog(self):
            QtWidgets.QMessageBox.information(
                self,
                "关于软件" if self.language == "zh_CN" else "About",
                (
                    "Damper Test Data Analyzer\n"
                    "减振器 / CDC 试验数据分析工具\n"
                    "V0.8.0"
                    if self.language == "zh_CN"
                    else "Damper Test Data Analyzer\nDamper / CDC test-data analysis\nV0.8.0"
                ),
            )

    return MainWindow


def main() -> int:
    _QtCore, QtWidgets, _pg = _qt_imports()
    MainWindow = _build_release_gui_classes_v080()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName(PRODUCT_NAME)
    app.setOrganizationName(COMPANY_EN)
    window = MainWindow()
    window.show()
    return int(app.exec())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
