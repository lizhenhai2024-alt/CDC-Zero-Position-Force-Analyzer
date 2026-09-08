from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

import numpy as np

from .dynamic_analysis import CURRENT, DISP, LOAD, TIME, VELOCITY
from .dynamic_export import export_hysteresis_xlsx, export_response_xlsx
from .gui import _qt_imports
from .gui_release_v071 import _build_release_gui_classes as _build_v071_classes
from .product_info import COMPANY_EN, PRODUCT_NAME


DASH_PATTERN = [8.0, 6.0]
PNG_EXPORT_SCALE = 3.0


def _nice_step(span: float, target_ticks: int = 6) -> float:
    """Return a conventional 1/2/5 engineering tick interval."""
    span = abs(float(span))
    if not math.isfinite(span) or span <= 0:
        return 1.0
    raw = span / max(int(target_ticks), 1)
    exponent = math.floor(math.log10(raw))
    fraction = raw / (10.0**exponent)
    if fraction <= 1.0:
        nice = 1.0
    elif fraction <= 2.0:
        nice = 2.0
    elif fraction <= 5.0:
        nice = 5.0
    else:
        nice = 10.0
    return nice * (10.0**exponent)


def _nice_bounds(values, include=(), padding_fraction: float = 0.06) -> tuple[float, float, float]:
    data = np.asarray(values, dtype=float)
    data = data[np.isfinite(data)]
    extras = np.asarray(list(include), dtype=float) if include else np.asarray([], dtype=float)
    extras = extras[np.isfinite(extras)]
    if extras.size:
        data = np.concatenate((data, extras)) if data.size else extras
    if not data.size:
        return -1.0, 1.0, 0.5

    lo = float(np.min(data))
    hi = float(np.max(data))
    span = hi - lo
    if not math.isfinite(span) or span <= 0:
        span = max(abs(lo), 1.0) * 0.2
        lo -= span / 2.0
        hi += span / 2.0

    padded_lo = lo - padding_fraction * span
    padded_hi = hi + padding_fraction * span
    step = _nice_step(padded_hi - padded_lo)
    rounded_lo = math.floor(padded_lo / step) * step
    rounded_hi = math.ceil(padded_hi / step) * step
    if rounded_hi <= rounded_lo:
        rounded_hi = rounded_lo + step
    return float(rounded_lo), float(rounded_hi), float(step)


def _build_release_gui_classes():
    QtCore, QtWidgets, _ = _qt_imports()
    from PySide6 import QtGui

    BaseMainWindow = _build_v071_classes()

    class MainWindow(BaseMainWindow):
        def __init__(self):
            super().__init__()
            self._configure_v072_exports()

        # ---------------------------- plot styling ----------------------------
        def _marker_pen_v07(self):
            pen = QtGui.QPen(QtGui.QColor(self._v07_response_marker_color))
            pen.setWidthF(0.85)
            pen.setStyle(QtCore.Qt.PenStyle.CustomDashLine)
            pen.setDashPattern(DASH_PATTERN)
            return pen

        def _prepare_axis_v072(self, plot):
            """Reserve enough room for complete axis labels and use readable fonts."""
            left = plot.getAxis("left")
            bottom = plot.getAxis("bottom")
            left.setWidth(112)
            bottom.setHeight(46)
            try:
                plot.layout.setContentsMargins(6, 4, 8, 6)
            except Exception:
                pass

        def _apply_auto_ticks_v072(self, plot, x_values, y_values, include_y=()):
            x_lo, x_hi, x_step = _nice_bounds(x_values, padding_fraction=0.01)
            y_lo, y_hi, y_step = _nice_bounds(y_values, include=include_y, padding_fraction=0.07)
            plot.getViewBox().disableAutoRange()
            plot.getViewBox().setRange(xRange=(x_lo, x_hi), yRange=(y_lo, y_hi), padding=0)
            try:
                plot.getAxis("bottom").setTickSpacing(major=x_step, minor=x_step / 5.0)
                plot.getAxis("left").setTickSpacing(major=y_step, minor=y_step / 5.0)
            except Exception:
                pass
            self._prepare_axis_v072(plot)
            return (x_lo, x_hi), (y_lo, y_hi)

        def _add_full_horizontal_v072(self, plot, x_left: float, x_right: float, y: float, label: str):
            if not all(np.isfinite(v) for v in (x_left, x_right, y)):
                return
            self._add_marker_segment_v07(plot, x_left, y, x_right, y)
            x_text = x_left + 0.008 * max(x_right - x_left, 1e-12)
            item = self._text_item_v07(label, x_text, y, anchor=(0, 1))
            item.setZValue(50)
            plot.addItem(item)

        def _add_full_vertical_v072(self, plot, x: float, y_bottom: float, y_top: float):
            if not all(np.isfinite(v) for v in (x, y_bottom, y_top)):
                return
            self._add_marker_segment_v07(plot, x, y_bottom, x, y_top)

        def _response_event_context_v072(self):
            controller = getattr(self, "dynamic_pages", None)
            if controller is None or controller.response_result is None or controller.response_result.events.empty:
                return None
            event_id = controller.response_event_combo.currentData()
            if event_id is None:
                event_id = int(controller.response_result.events["Event ID"].iloc[0])
            row = controller.response_result.events[
                controller.response_result.events["Event ID"] == event_id
            ].iloc[0]
            full_data = controller.response_result.processed[
                controller.response_result.processed[TIME].between(row["Segment Start s"], row["Segment End s"])
            ].copy()
            if "Block ID" in full_data.columns and "Block ID" in row:
                full_data = full_data[full_data["Block ID"] == int(row["Block ID"])]
            if full_data.empty:
                return None
            full_data = full_data.sort_values(TIME)
            return controller, row, full_data

        def _draw_response_detail_v07(self):
            """Stage detail: Current / Force / Velocity for both BMW and Audi."""
            context = self._response_event_context_v072()
            if context is None:
                return
            controller, row, full_data = context

            full_t = full_data[TIME].to_numpy(float)
            full_force = full_data[LOAD].to_numpy(float)
            full_current = full_data[CURRENT].to_numpy(float)
            t0 = float(row["t0 s"])
            t90 = float(row.get("t90 s", np.nan))
            f100_time = self._first_progress_time(
                full_t,
                full_force,
                float(row["F0 N"]),
                float(row["F100 N"]),
                t0,
                fraction=0.995,
            )
            i100_time = self._first_progress_time(
                full_t,
                full_current,
                float(row["Current Start A"]),
                float(row["Current End A"]),
                t0,
                fraction=0.995,
            )

            segment_start = float(row["Segment Start s"])
            segment_end = float(row["Segment End s"])
            detail_start = max(segment_start, t0 - 0.020)
            response_end_candidates = [
                value for value in (t90, f100_time, i100_time, t0 + 0.020) if np.isfinite(value)
            ]
            detail_end = min(segment_end, max(response_end_candidates) + 0.012)
            if detail_end - detail_start < 0.040:
                detail_end = min(segment_end, detail_start + 0.040)

            data = full_data[full_data[TIME].between(detail_start, detail_end)].copy()
            if data.empty:
                data = full_data
                detail_start = float(full_t[0])
                detail_end = float(full_t[-1])

            t = data[TIME].to_numpy(float)
            force = data[LOAD].to_numpy(float)
            current = data[CURRENT].to_numpy(float)
            displacement = data[DISP].to_numpy(float)
            velocity = (
                data[VELOCITY].to_numpy(float)
                if VELOCITY in data.columns
                else np.gradient(displacement, t) / 1000.0
            )

            controller.response_plot_area.clear()
            stage = controller._display_value("Stage", row["Stage"])
            direction = controller._display_value("Direction", row["Direction"])

            current_plot = controller.response_plot_area.addPlot(row=0, col=0)
            current_plot.setTitle(
                self._text_v07(
                    f"电流｜{stage}｜{direction}",
                    f"Current | {row['Stage']} | {row['Direction']}",
                ),
                size="11pt",
            )
            controller._axis_style(current_plot, self._text_v07("阀电流", "Valve current"), "A")
            current_plot.plot(t, current, pen=controller._curve_pen(1.55))

            force_plot = controller.response_plot_area.addPlot(row=1, col=0)
            force_plot.setXLink(current_plot)
            force_plot.setTitle(self._text_v07("阻尼力", "Damping Force"), size="11pt")
            controller._axis_style(force_plot, self._text_v07("阻尼力", "Damping force"), "N")
            force_plot.plot(t, force, pen=controller._curve_pen(1.65))

            velocity_plot = controller.response_plot_area.addPlot(row=2, col=0)
            velocity_plot.setXLink(current_plot)
            velocity_plot.setTitle(self._text_v07("速度", "Velocity"), size="11pt")
            controller._axis_style(velocity_plot, self._text_v07("速度", "Velocity"), "m/s")
            velocity_plot.plot(t, velocity, pen=controller._curve_pen(1.45))

            plots = [current_plot, force_plot, velocity_plot]
            for plot in plots:
                plot.setMinimumHeight(235)
                self._prepare_axis_v072(plot)

            # Current evaluation lines are deliberately full-width. I10 has a vertical
            # evaluation line to the blue intersection; wording is simplified to I10/I100.
            trigger_current = float(row["Trigger Current A"])
            start_current = float(row["Current Start A"])
            end_current = float(row["Current End A"])
            self._add_full_horizontal_v072(current_plot, detail_start, detail_end, trigger_current, "I10%")
            self._add_full_horizontal_v072(current_plot, detail_start, detail_end, end_current, "I100%")
            self._add_vertical_to_intersection_v07(current_plot, t0, 0.0, trigger_current, "t0")
            self._add_intersection_v07(current_plot, t0, trigger_current)
            if np.isfinite(i100_time):
                self._add_intersection_v07(current_plot, i100_time, end_current)

            # Force horizontal and vertical evaluation lines both terminate at the
            # evaluation point, matching the customer-style response diagram.
            force_left = detail_start
            f0 = float(row["F0 N"])
            self._add_horizontal_to_intersection_v07(force_plot, force_left, t0, f0, "F0")
            self._add_intersection_v07(force_plot, t0, f0)
            threshold_specs = (
                ("F1 N", "t1 s", "F1%", "t1%"),
                ("F10 N", "t10 s", "F10%", "t10%"),
                ("F63 N", "t63 s", "F63%", "t63%"),
                ("F90 N", "t90 s", "F90%", "t90%"),
            )
            for force_key, time_key, force_label, time_label in threshold_specs:
                force_value = float(row.get(force_key, np.nan))
                time_value = float(row.get(time_key, np.nan))
                if not (np.isfinite(force_value) and np.isfinite(time_value)):
                    continue
                self._add_horizontal_to_intersection_v07(
                    force_plot, force_left, time_value, force_value, force_label
                )
                self._add_vertical_to_intersection_v07(
                    force_plot, time_value, 0.0, force_value, time_label
                )
                self._add_intersection_v07(force_plot, time_value, force_value)
            if np.isfinite(f100_time):
                f100 = float(row["F100 N"])
                self._add_horizontal_to_intersection_v07(force_plot, force_left, f100_time, f100, "F100%")
                self._add_vertical_to_intersection_v07(force_plot, f100_time, 0.0, f100, None)
                self._add_intersection_v07(force_plot, f100_time, f100)

            direction_text = self._text_v07(
                "复原 (+)" if row["Direction"] == "Rebound" else "压缩 (-)",
                "Rebound (+)" if row["Direction"] == "Rebound" else "Compression (-)",
            )
            force_label_y = float(np.nanmax(force)) if row["Direction"] == "Rebound" else float(np.nanmin(force))
            force_plot.addItem(
                self._text_item_v07(
                    direction_text,
                    detail_start + 0.02 * max(detail_end - detail_start, 1e-12),
                    force_label_y,
                    anchor=(0, 1),
                )
            )

            target_velocity = float(row.get("Target Velocity m/s", np.nan))
            if np.isfinite(target_velocity):
                self._add_full_horizontal_v072(
                    velocity_plot,
                    detail_start,
                    detail_end,
                    target_velocity,
                    self._text_v07(
                        f"目标速度 {target_velocity:.4f} m/s",
                        f"Target {target_velocity:.4f} m/s",
                    ),
                )

            current_include = (0.0, start_current, trigger_current, end_current)
            force_include = (
                0.0,
                f0,
                row.get("F1 N", np.nan),
                row.get("F10 N", np.nan),
                row.get("F63 N", np.nan),
                row.get("F90 N", np.nan),
                row.get("F100 N", np.nan),
            )
            velocity_include = (target_velocity,) if np.isfinite(target_velocity) else ()

            x_range, current_range = self._apply_auto_ticks_v072(
                current_plot, t, current, include_y=current_include
            )
            _x, force_range = self._apply_auto_ticks_v072(force_plot, t, force, include_y=force_include)
            _x, velocity_range = self._apply_auto_ticks_v072(
                velocity_plot, t, velocity, include_y=velocity_include
            )
            # X axes are linked; enforce identical rounded X range after all three calls.
            current_plot.getViewBox().setRange(xRange=x_range, yRange=current_range, padding=0)
            force_plot.getViewBox().setRange(yRange=force_range, padding=0)
            velocity_plot.getViewBox().setRange(yRange=velocity_range, padding=0)

            self._response_plots_v07 = plots
            self._capture_response_ranges_v07()
            self._set_response_mouse_mode_v07(self._response_mouse_mode_v07)

        def _draw_response_overview(self):
            controller = getattr(self, "dynamic_pages", None)
            if controller is None or controller.response_result is None:
                return
            data = controller.response_result.processed.copy().sort_values(TIME)
            if data.empty:
                return

            plot_area = controller.response_plot_area
            plot_area.clear()
            t = data[TIME].to_numpy(float)
            specs = (
                (LOAD, self._text_v07("压缩<--阻尼力-->复原", "Compression <-- Damping force --> Rebound"), "N"),
                (CURRENT, self._text_v07("阀电流", "Valve current"), "A"),
                (DISP, self._text_v07("位移", "Displacement"), "mm"),
            )
            plots = []
            previous = None
            for row_index, (column, label, unit) in enumerate(specs):
                plot = plot_area.addPlot(row=row_index, col=0)
                controller._axis_style(plot, label, unit)
                self._prepare_axis_v072(plot)
                plot.setMinimumHeight(235)
                plot.plot(t, data[column].to_numpy(float), pen=controller._curve_pen(1.15))
                if previous is not None:
                    plot.setXLink(previous)
                previous = plot
                plots.append(plot)

            plots[0].setTitle(
                self._text_v07("响应时间试验全流程总览", "Full response-test overview"),
                size="12pt",
            )

            # Stage-level boundaries only: retain all events for analysis, but avoid a
            # forest of E1..En markers in the overview. Consecutive events with the
            # same current-stage name are grouped visually.
            events = controller.response_result.events.sort_values("t0 s")
            last_stage = None
            for _, event in events.iterrows():
                event_time = float(event.get("t0 s", np.nan))
                stage = controller._display_value("Stage", event.get("Stage", ""))
                if not np.isfinite(event_time) or stage == last_stage:
                    continue
                for plot, (column, _label, _unit) in zip(plots, specs):
                    y_values = data[column].to_numpy(float)
                    if len(y_values):
                        self._add_full_vertical_v072(
                            plot,
                            event_time,
                            float(np.nanmin(y_values)),
                            float(np.nanmax(y_values)),
                        )
                current_values = data[CURRENT].to_numpy(float)
                if len(current_values):
                    plots[1].addItem(
                        self._text_item_v07(
                            stage,
                            event_time,
                            float(np.nanmax(current_values)),
                            anchor=(0, 0),
                        )
                    )
                last_stage = stage

            x_range = None
            y_ranges = []
            for plot, (column, _label, _unit) in zip(plots, specs):
                xr, yr = self._apply_auto_ticks_v072(plot, t, data[column].to_numpy(float))
                if x_range is None:
                    x_range = xr
                y_ranges.append(yr)
            if x_range is not None:
                plots[0].getViewBox().setRange(xRange=x_range, padding=0)
            for plot, yr in zip(plots, y_ranges):
                plot.getViewBox().setRange(yRange=yr, padding=0)

            self._response_plots_v07 = plots
            self._capture_response_ranges_v07()
            self._set_response_mouse_mode_v07(self._response_mouse_mode_v07)

        # ---------------------------- high-resolution image export ----------------------------
        def _save_widget_highres_v072(self, widget, path: str | Path, scale: float = PNG_EXPORT_SCALE) -> Path:
            out = Path(path).with_suffix(".png")
            out.parent.mkdir(parents=True, exist_ok=True)
            scale = max(float(scale), 1.0)
            size = widget.size()
            width = max(1, int(round(size.width() * scale)))
            height = max(1, int(round(size.height() * scale)))
            image = QtGui.QImage(width, height, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
            background = getattr(self, "_plot_background_color", "#ffffff")
            image.fill(QtGui.QColor(background))
            painter = QtGui.QPainter(image)
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
            painter.scale(scale, scale)
            widget.render(painter)
            painter.end()
            if not image.save(str(out), "PNG"):
                raise RuntimeError(f"Failed to save PNG: {out}")
            return out

        def _configure_v072_exports(self):
            controller = getattr(self, "dynamic_pages", None)
            if controller is None:
                return
            for button, callback in (
                (controller.response_export_button, self._export_response_excel_v072),
                (controller.response_export_image_button, self._export_response_png_v072),
                (controller.hysteresis_export_button, self._export_hysteresis_excel_v072),
                (controller.hysteresis_export_image_button, self._export_hysteresis_png_v072),
            ):
                try:
                    button.clicked.disconnect()
                except (TypeError, RuntimeError):
                    pass
                button.clicked.connect(callback)

        def _export_response_png_v072(self):
            controller = self.dynamic_pages
            if controller.response_result is None:
                return
            event_id = controller.response_event_combo.currentData() or 1
            stem = controller.response_path.stem if controller.response_path else "response"
            view = self.response_view_mode.currentData() if self.response_view_mode is not None else "detail"
            suffix = "overview" if view == "overview" else f"event_{event_id}"
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                self._text_v07("导出高清响应图片", "Export high-resolution response image"),
                f"{stem}_response_{suffix}.png",
                "PNG (*.png)",
            )
            if not path:
                return
            try:
                self._save_widget_highres_v072(controller.response_plot_area, path)
            except Exception as exc:
                QtWidgets.QMessageBox.critical(self, self._text_v07("导出错误", "Export error"), str(exc))

        def _export_hysteresis_png_v072(self):
            controller = self.dynamic_pages
            if controller.hysteresis_result is None:
                return
            stem = controller.hysteresis_path.stem if controller.hysteresis_path else "hysteresis"
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                self._text_v07("导出高清迟滞图片", "Export high-resolution hysteresis image"),
                f"{stem}_hysteresis.png",
                "PNG (*.png)",
            )
            if not path:
                return
            try:
                self._save_widget_highres_v072(controller.hysteresis_plot_area, path)
            except Exception as exc:
                QtWidgets.QMessageBox.critical(self, self._text_v07("导出错误", "Export error"), str(exc))

        def _export_response_excel_v072(self):
            controller = self.dynamic_pages
            if controller.response_result is None:
                return
            stem = controller.response_path.stem if controller.response_path else "response"
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                self._text_v07("导出全部响应结果与图形", "Export all response results and figures"),
                f"{stem}_response.xlsx",
                "Excel (*.xlsx)",
            )
            if not path:
                return

            previous_event = controller.response_event_combo.currentIndex()
            previous_view = self.response_view_mode.currentData() if self.response_view_mode is not None else "detail"
            try:
                with tempfile.TemporaryDirectory(prefix="damper_response_export_") as temp_dir:
                    temp = Path(temp_dir)
                    stage_figures = []

                    # Full-process overview figure.
                    if self.response_view_mode is not None:
                        self.response_view_mode.setCurrentIndex(self.response_view_mode.findData("overview"))
                    self._draw_response_overview()
                    QtWidgets.QApplication.processEvents()
                    overview_path = self._save_widget_highres_v072(
                        controller.response_plot_area, temp / "response_overview.png"
                    )

                    # Every identified response stage/direction event gets its own figure.
                    if self.response_view_mode is not None:
                        self.response_view_mode.setCurrentIndex(self.response_view_mode.findData("detail"))
                    for index in range(controller.response_event_combo.count()):
                        controller.response_event_combo.setCurrentIndex(index)
                        self._draw_response_detail_v07()
                        QtWidgets.QApplication.processEvents()
                        event_id = controller.response_event_combo.currentData()
                        title = controller.response_event_combo.currentText() or f"Event {event_id}"
                        image_path = self._save_widget_highres_v072(
                            controller.response_plot_area,
                            temp / f"response_stage_{index + 1:03d}.png",
                        )
                        stage_figures.append((title, image_path))

                    export_response_xlsx(
                        controller.response_result,
                        path,
                        include_processed=True,
                        stage_figures=stage_figures,
                        overview_figure=(
                            self._text_v07("全流程总览", "Full-process overview"),
                            overview_path,
                        ),
                        language=self.language,
                    )
            except Exception as exc:
                QtWidgets.QMessageBox.critical(self, self._text_v07("导出错误", "Export error"), str(exc))
            finally:
                if self.response_view_mode is not None:
                    restore_view = self.response_view_mode.findData(previous_view)
                    if restore_view >= 0:
                        self.response_view_mode.setCurrentIndex(restore_view)
                if 0 <= previous_event < controller.response_event_combo.count():
                    controller.response_event_combo.setCurrentIndex(previous_event)
                self._refresh_response_v07()

        def _export_hysteresis_excel_v072(self):
            controller = self.dynamic_pages
            if controller.hysteresis_result is None:
                return
            stem = controller.hysteresis_path.stem if controller.hysteresis_path else "hysteresis"
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                self._text_v07("导出全部迟滞结果与图形", "Export all hysteresis results and figures"),
                f"{stem}_hysteresis.xlsx",
                "Excel (*.xlsx)",
            )
            if not path:
                return
            try:
                with tempfile.TemporaryDirectory(prefix="damper_hysteresis_export_") as temp_dir:
                    image_path = self._save_widget_highres_v072(
                        controller.hysteresis_plot_area,
                        Path(temp_dir) / "hysteresis_all_stages.png",
                    )
                    export_hysteresis_xlsx(
                        controller.hysteresis_result,
                        path,
                        include_processed=False,
                        figures=[(
                            self._text_v07("全部迟滞阶段", "All hysteresis stages"),
                            image_path,
                        )],
                        language=self.language,
                    )
            except Exception as exc:
                QtWidgets.QMessageBox.critical(self, self._text_v07("导出错误", "Export error"), str(exc))

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
