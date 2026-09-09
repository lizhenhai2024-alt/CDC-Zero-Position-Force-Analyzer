from __future__ import annotations

import sys

from . import gui_release_v083 as _v083_module
from .dynamic_gui_v084 import DynamicPagesController
from .gui import _qt_imports
from .gui_release_v083 import _build_release_gui_classes_v083
from .product_info import COMPANY_EN, PRODUCT_NAME


def _build_release_gui_classes_v084():
    _QtCore, QtWidgets, _pg = _qt_imports()
    BaseMainWindow = _build_release_gui_classes_v083()

    class MainWindow(BaseMainWindow):
        def __init__(self):
            # V0.8.3 injects its controller during construction. Replace that
            # module-level controller temporarily so the existing release chain
            # builds the same UI with the V0.8.4 response-plot implementation.
            previous_controller = _v083_module.DynamicPagesController
            _v083_module.DynamicPagesController = DynamicPagesController
            try:
                super().__init__()
            finally:
                _v083_module.DynamicPagesController = previous_controller

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
    MainWindow = _build_release_gui_classes_v084()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName(PRODUCT_NAME)
    app.setOrganizationName(COMPANY_EN)
    window = MainWindow()
    window.show()
    return int(app.exec())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
