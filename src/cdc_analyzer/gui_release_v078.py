from __future__ import annotations

import sys

from . import gui_release_v076 as _v076_module
from . import gui_release_v077 as _v077_module
from .dynamic_gui_v078 import DynamicPagesController as _ControllerV078
from .gui import _qt_imports
from .product_info import COMPANY_EN, PRODUCT_NAME

DynamicPagesController = _ControllerV078


def _build_release_gui_classes_v078():
    # Build the inherited shell first, then re-assert the exact V0.7.8 dynamic
    # controller before each window instance is initialized. This avoids newer
    # release imports mutating older-version regression behavior.
    _QtCore, QtWidgets, _pg = _qt_imports()
    BaseMainWindow = _v077_module._build_release_gui_classes_v077()

    class MainWindow(BaseMainWindow):
        def __init__(self):
            _v077_module.DynamicPagesController = _ControllerV078
            _v076_module.DynamicPagesController = _ControllerV078
            super().__init__()

        def _show_about_dialog(self):
            QtWidgets.QMessageBox.information(
                self,
                "关于软件" if self.language == "zh_CN" else "About",
                (
                    "Damper Test Data Analyzer\n"
                    "减振器 / CDC 试验数据分析工具\n"
                    "V0.7.8"
                    if self.language == "zh_CN"
                    else "Damper Test Data Analyzer\nDamper / CDC test-data analysis\nV0.7.8"
                ),
            )

    return MainWindow


def main() -> int:
    _QtCore, QtWidgets, _pg = _qt_imports()
    MainWindow = _build_release_gui_classes_v078()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName(PRODUCT_NAME)
    app.setOrganizationName(COMPANY_EN)
    window = MainWindow()
    window.show()
    return int(app.exec())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
