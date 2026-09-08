from __future__ import annotations

import math
import sys
from pathlib import Path

from .dynamic_analysis import load_dynamic_test_data
from .gui import _qt_imports
from .gui_release_v07 import _build_release_gui_classes as _build_v07_classes
from .i18n import tr
from .product_info import COMPANY_EN, PRODUCT_NAME


# CDC response-state convention for this product family.
# 0.30 A is the soft endpoint, 1.60 A is the hard endpoint, and all
# intermediate setpoints (for example 0.80 / 0.90 / 0.95 A) are Medium.
# The small endpoint bands absorb normal measured-current feedback scatter.
SOFT_CURRENT_MAX_A = 0.45
HARD_CURRENT_MIN_A = 1.45


def classify_response_current_state(current_a: float) -> str:
    """Classify the CDC response state from measured current, not force level."""
    value = float(current_a)
    if not math.isfinite(value):
        return "Unknown"
    if value <= SOFT_CURRENT_MAX_A:
        return "Soft"
    if value >= HARD_CURRENT_MIN_A:
        return "Hard"
    return "Medium"


def response_stage_name(current_start_a: float, current_end_a: float) -> str:
    """Return the response-stage label using the product current convention."""
    return (
        f"{classify_response_current_state(current_start_a)} → "
        f"{classify_response_current_state(current_end_a)}"
    )


def _build_release_gui_classes():
    QtCore, QtWidgets, _ = _qt_imports()
    BaseMainWindow = _build_v07_classes()

    class MainWindow(BaseMainWindow):
        def __init__(self):
            self._v071_ready = False
            self._v071_response_analyze_base = None
            self._v071_hysteresis_analyze_base = None
            super().__init__()
            self._remove_help_tab_v071()
            self._configure_shared_import_v071()
            self._v071_ready = True
            self._apply_shared_language_v071()

        def _remove_help_tab_v071(self):
            """Remove the Help tab completely; the V0.7 toolbar button is already hidden."""
            help_page = getattr(self, "help_page", None)
            if help_page is None:
                return
            index = self.tabs.indexOf(help_page)
            if index >= 0:
                self.tabs.removeTab(index)

        def _configure_shared_import_v071(self):
            """Use the left-side Data File import as the single source for all analyses."""
            controller = getattr(self, "dynamic_pages", None)
            if controller is None:
                return

            # Response-time and hysteresis no longer expose their own import controls.
            for name in (
                "response_open_button",
                "response_file_label",
                "hysteresis_open_button",
                "hysteresis_file_label",
            ):
                widget = getattr(controller, name, None)
                if widget is not None:
                    widget.hide()

            self._v071_response_analyze_base = controller.analyze_response
            self._v071_hysteresis_analyze_base = controller.analyze_hysteresis

            # The controller connected these buttons before this release layer existed.
            # Reconnect them to wrappers that always consume self.dataset from the left panel.
            try:
                controller.response_analyze_button.clicked.disconnect()
            except (TypeError, RuntimeError):
                pass
            controller.response_analyze_button.clicked.connect(self._analyze_response_shared_v071)

            try:
                controller.hysteresis_analyze_button.clicked.disconnect()
            except (TypeError, RuntimeError):
                pass
            controller.hysteresis_analyze_button.clicked.connect(self._analyze_hysteresis_shared_v071)

            self._sync_dynamic_source_v071(clear_results=False)

        def open_file(self):
            """Single import path for damping-force, response-time and hysteresis analyses."""
            filename, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                tr(self.language, "open_test_data"),
                "",
                tr(self.language, "test_data_filter"),
            )
            if not filename:
                return
            try:
                # This is a superset of load_test_data(): normal files use the original
                # parser; headerless four-channel DAT files retain the dynamic fallback.
                self.dataset = load_dynamic_test_data(filename)
            except Exception as exc:
                QtWidgets.QMessageBox.critical(self, tr(self.language, "import_error"), str(exc))
                return

            self.current_path = Path(filename)
            self._update_file_meta()
            self._sync_dynamic_source_v071(clear_results=True)

            # Preserve the existing center-stroke-force workflow: importing data still
            # refreshes the damping-force analysis automatically.
            self.analyze()

        def _sync_dynamic_source_v071(self, clear_results: bool):
            controller = getattr(self, "dynamic_pages", None)
            if controller is None:
                return

            controller.response_dataset = self.dataset
            controller.hysteresis_dataset = self.dataset
            controller.response_path = self.current_path
            controller.hysteresis_path = self.current_path

            has_data = self.dataset is not None
            controller.response_analyze_button.setEnabled(has_data)
            controller.hysteresis_analyze_button.setEnabled(has_data)

            if clear_results:
                controller.response_result = None
                controller.hysteresis_result = None
                controller.response_event_combo.clear()
                controller.response_table.setRowCount(0)
                controller.hysteresis_summary_table.setRowCount(0)
                controller.hysteresis_run_table.setRowCount(0)
                controller.response_plot_area.clear()
                controller.hysteresis_plot_area.clear()
                self._response_plots_v07 = []
                self._response_initial_ranges_v07 = []

            if has_data and self.current_path is not None:
                name = self.current_path.name
                controller.response_status.setText(
                    self._text_shared_v071(
                        f"使用左侧数据文件：{name}",
                        f"Using left-side data file: {name}",
                    )
                )
                controller.hysteresis_status.setText(
                    self._text_shared_v071(
                        f"使用左侧数据文件：{name}",
                        f"Using left-side data file: {name}",
                    )
                )
            elif not has_data:
                message = self._text_shared_v071(
                    "请先在左侧“数据文件”中导入试验数据。",
                    "Import test data from the left-side Data File panel first.",
                )
                controller.response_status.setText(message)
                controller.hysteresis_status.setText(message)

        def _analyze_response_shared_v071(self):
            controller = getattr(self, "dynamic_pages", None)
            if controller is None:
                return
            if self.dataset is None:
                QtWidgets.QMessageBox.information(
                    self,
                    self._text_shared_v071("响应时间", "Response Time"),
                    self._text_shared_v071(
                        "请先在左侧“数据文件”中导入试验数据。",
                        "Import test data from the left-side Data File panel first.",
                    ),
                )
                return

            self._sync_dynamic_source_v071(clear_results=False)
            controller.response_result = None
            if self._v071_response_analyze_base is not None:
                self._v071_response_analyze_base()
            self._apply_response_stage_mapping_v071()

        def _apply_response_stage_mapping_v071(self):
            controller = getattr(self, "dynamic_pages", None)
            if controller is None or controller.response_result is None:
                return
            events = controller.response_result.events
            if events.empty:
                return

            events = events.copy()
            events["Stage"] = [
                response_stage_name(start, end)
                for start, end in zip(events["Current Start A"], events["Current End A"])
            ]
            controller.response_result.events = events
            controller.response_result.settings["Stage Classification"] = (
                "current-based: <=0.45 A Soft; >=1.45 A Hard; otherwise Medium"
            )

            controller._fill_table(controller.response_table, controller._response_display_frame())
            controller._rebuild_response_event_combo()
            controller.refresh_response_plot()

            base_status = controller.response_status.text().strip()
            mapping_note = self._text_shared_v071(
                "电流状态：0.3 A=软，1.6 A=硬，其余中间电流=中间。",
                "Current states: 0.3 A=Soft, 1.6 A=Hard, intermediate setpoints=Medium.",
            )
            controller.response_status.setText(
                f"{base_status}；{mapping_note}" if self.language == "zh_CN" else f"{base_status}; {mapping_note}"
            )

        def _analyze_hysteresis_shared_v071(self):
            controller = getattr(self, "dynamic_pages", None)
            if controller is None:
                return
            if self.dataset is None:
                QtWidgets.QMessageBox.information(
                    self,
                    self._text_shared_v071("迟滞", "Hysteresis"),
                    self._text_shared_v071(
                        "请先在左侧“数据文件”中导入试验数据。",
                        "Import test data from the left-side Data File panel first.",
                    ),
                )
                return

            self._sync_dynamic_source_v071(clear_results=False)
            controller.hysteresis_result = None
            if self._v071_hysteresis_analyze_base is not None:
                self._v071_hysteresis_analyze_base()

        def _apply_v07_language(self):
            super()._apply_v07_language()
            if getattr(self, "_v071_ready", False):
                self._apply_shared_language_v071()

        def _apply_shared_language_v071(self):
            controller = getattr(self, "dynamic_pages", None)
            if controller is None:
                return

            tooltip = self._text_shared_v071(
                "响应时间与迟滞均使用左侧“数据文件”导入的同一份原始数据。",
                "Response-time and hysteresis analyses use the same raw data imported from the left Data File panel.",
            )
            controller.response_analyze_button.setToolTip(tooltip)
            controller.hysteresis_analyze_button.setToolTip(tooltip)

            if self.dataset is None:
                self._sync_dynamic_source_v071(clear_results=False)

        def _text_shared_v071(self, zh: str, en: str) -> str:
            return zh if self.language == "zh_CN" else en

    return MainWindow


def main() -> int:
    _, QtWidgets, _ = _qt_imports()
    MainWindow = _build_release_gui_classes()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName(PRODUCT_NAME)
    app.setOrganizationName(COMPANY_EN)
    window = MainWindow()
    window.show()
    return int(app.exec())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
