from __future__ import annotations

import sys

from . import gui_release_v076 as _v076_module
from .dynamic_gui_v081 import DynamicPagesController
from .gui import _qt_imports
from .product_info import COMPANY_EN, PRODUCT_NAME


def _build_release_gui_classes_v081():
    _QtCore, QtWidgets, _pg = _qt_imports()
    BaseMainWindow = _v076_module._build_release_gui_classes_v076()

    class MainWindow(BaseMainWindow):
        def __init__(self):
            # Inject the latest dynamic controller only for this window instance.
            # Restoring the historical module global afterwards prevents V0.8.x
            # imports from contaminating V0.7.x regression tests.
            previous_controller = _v076_module.DynamicPagesController
            _v076_module.DynamicPagesController = DynamicPagesController
            try:
                super().__init__()
            finally:
                _v076_module.DynamicPagesController = previous_controller

        def _show_about_dialog(self):
            QtWidgets.QMessageBox.information(
                self,
                "关于软件" if self.language == "zh_CN" else "About",
                (
                    "Damper Test Data Analyzer\n"
                    "减振器 / CDC 试验数据分析工具\n"
                    "V0.8.1"
                    if self.language == "zh_CN"
                    else "Damper Test Data Analyzer\nDamper / CDC test-data analysis\nV0.8.1"
                ),
            )

    return MainWindow


def main() -> int:
    _QtCore, QtWidgets, _pg = _qt_imports()
    MainWindow = _build_release_gui_classes_v081()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName(PRODUCT_NAME)
    app.setOrganizationName(COMPANY_EN)
    window = MainWindow()
    window.show()
    return int(app.exec())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
