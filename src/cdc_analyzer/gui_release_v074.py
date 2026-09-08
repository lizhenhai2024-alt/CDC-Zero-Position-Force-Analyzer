from __future__ import annotations

import sys

import numpy as np

from .dynamic_analysis import ResponseConfig, ResponseStandard
from .gui import _qt_imports
from .gui_release_v072 import _nice_bounds
from .gui_release_v073 import _build_release_gui_classes as _build_v073_classes
from .product_info import COMPANY_EN, PRODUCT_NAME
from .response_target_velocity_v074 import analyze_response_time_target_velocity

GRID_ALPHA_V074 = 0.11


def _major_tick_levels(step: float) -> list[tuple[float, float]]:
    return [(float(step), 0.0)]


def _build_release_gui_classes():
    QtCore, QtWidgets, _ = _qt_imports()
    BaseMainWindow = _build_v073_classes()

    class MainWindow(BaseMainWindow):
        """V0.7.4 response evaluation and plot cleanup.

        - only OEM target-speed current steps are evaluated;
        - F100 and switching thresholds are recalculated inside the contiguous
          target-speed window;
        - plot grids use major engineering ticks only, removing the dense blue
          minor-grid stripes seen on high-resolution response plots.
        """

        def _apply_auto_ticks_v072(self, plot, x_values, y_values, include_y=()):
            x_lo, x_hi, x_step = _nice_bounds(x_values, padding_fraction=0.01)
            y_lo, y_hi, y_step = _nice_bounds(y_values, include=include_y, padding_fraction=0.07)
            plot.getViewBox().disableAutoRange()
            plot.getViewBox().setRange(xRange=(x_lo, x_hi), yRange=(y_lo, y_hi), padding=0)

            # pyqtgraph draws grid lines at every tick level. V0.7.2 explicitly
            # requested minor ticks at 1/5 of the engineering step, which produced
            # dense horizontal stripes. Supplying a single level keeps only the
            # major 1/2/5 engineering grid.
            bottom = plot.getAxis("bottom")
            left = plot.getAxis("left")
            try:
                bottom.setTickSpacing(levels=_major_tick_levels(x_step))
                left.setTickSpacing(levels=_major_tick_levels(y_step))
            except TypeError:
                # Compatibility fallback for older pyqtgraph builds.
                bottom.setTickSpacing(major=x_step, minor=None)
                left.setTickSpacing(major=y_step, minor=None)
            plot.showGrid(x=True, y=True, alpha=GRID_ALPHA_V074)
            self._prepare_axis_v072(plot)
            return (x_lo, x_hi), (y_lo, y_hi)

        def _analyze_response_shared_v071(self):
            controller = getattr(self, "dynamic_pages", None)
            if controller is None:
                return
            if self.dataset is None:
                QtWidgets.QMessageBox.information(
                    self,
                    "响应时间" if self.language == "zh_CN" else "Response Time",
                    (
                        "请先在左侧“数据文件”中导入试验数据。"
                        if self.language == "zh_CN"
                        else "Import test data from the left-side Data File panel first."
                    ),
                )
                return

            self._sync_dynamic_source_v071(clear_results=False)
            controller.response_result = None
            try:
                standard = ResponseStandard(controller.response_standard.currentData())
                limit = controller.response_t90_limit.value() or None
                config = ResponseConfig(
                    standard=standard,
                    trigger_fraction=controller.response_trigger.value() / 100.0,
                    end_average_fraction=controller.response_end_fraction.value() / 100.0,
                    t90_limit_ms=limit,
                )
                result = analyze_response_time_target_velocity(self.dataset, config)
                controller.response_result = result
                controller._fill_table(controller.response_table, controller._response_display_frame())
                controller._rebuild_response_event_combo()
                controller.refresh_response_plot()

                raw_count = int(result.settings.get("Detected Raw Events", len(result.events)))
                accepted_count = int(result.settings.get("Accepted Target-Speed Events", len(result.events)))
                rejected_count = int(result.settings.get("Rejected Non-target Events", 0))
                target_values = result.settings.get("OEM Target Speeds m/s", ())
                targets_text = "/".join(f"{float(value):g}" for value in target_values)
                sample_rate = float(result.events["Sample Rate Hz"].iloc[0])
                if self.language == "zh_CN":
                    controller.response_status.setText(
                        f"目标速度响应：检测 {raw_count} 个电流切换，保留 {accepted_count} 个；"
                        f"忽略 {rejected_count} 个非目标速度切换；目标速度 {targets_text} m/s；"
                        f"采样率约 {sample_rate:.2f} Hz"
                    )
                else:
                    controller.response_status.setText(
                        f"Target-speed response: {raw_count} current steps detected, {accepted_count} retained; "
                        f"{rejected_count} non-target step(s) ignored; targets {targets_text} m/s; "
                        f"sample rate ≈ {sample_rate:.2f} Hz"
                    )

                # Keep the product-family current-state mapping introduced in V0.7.1:
                # 0.3 A Soft, 1.6 A Hard, intermediate current setpoints Medium.
                self._apply_response_stage_mapping_v071()
            except Exception as exc:
                QtWidgets.QMessageBox.critical(
                    self,
                    "分析错误" if self.language == "zh_CN" else "Analysis error",
                    str(exc),
                )

        def _draw_response_detail_v07(self):
            super()._draw_response_detail_v07()
            # The target-speed evaluator trims Segment Start/End to the contiguous
            # nominal-speed window, so the displayed velocity trace is now centered
            # on the actual response condition rather than acceleration/reversal data.
            plots = self._response_plot_items_v07()
            if len(plots) >= 3:
                velocity_plot = plots[-1]
                velocity_plot.showGrid(x=True, y=True, alpha=GRID_ALPHA_V074)

        def _draw_response_overview(self):
            super()._draw_response_overview()
            for plot in self._response_plot_items_v07():
                plot.showGrid(x=True, y=True, alpha=GRID_ALPHA_V074)

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
