from __future__ import annotations

import sys

import numpy as np

from .dynamic_analysis import CURRENT, DISP, LOAD, TIME, VELOCITY
from .gui import _qt_imports
from .gui_release import _build_release_gui_classes as _build_v06_classes
from .gui_release import _release_help_html
from .product_info import COMPANY_EN, PRODUCT_NAME


RESPONSE_MARKER_BLUE = "#1565C0"


def _help_html_v07(language: str) -> str:
    text = _release_help_html(language)
    if language == "zh_CN":
        return text.replace("专业帮助", "帮助")
    return text.replace("Professional Help", "Help")


def _build_release_gui_classes():
    QtCore, QtWidgets, _ = _qt_imports()
    BaseMainWindow = _build_v06_classes()

    class MainWindow(BaseMainWindow):
        def __init__(self):
            self._v07_ready = False
            self._v07_toolbar_spacer = None
            self._v07_response_base_refresh = None
            self.response_view_label = None
            self.response_view_mode = None
            self.response_zoom_in_button = None
            self.response_zoom_out_button = None
            self.response_box_zoom_button = None
            self.response_pan_button = None
            self.response_reset_button = None
            self._response_plots_v07 = []
            self._response_initial_ranges_v07 = []
            self._response_mouse_mode_v07 = "pan"
            self._v07_response_marker_color = RESPONSE_MARKER_BLUE
            super().__init__()
            self._configure_v07_toolbar()
            self._configure_v07_response_overview()
            self._v07_ready = True
            self._apply_v07_language()

        def _configure_v07_toolbar(self):
            toolbar = self.release_language_toolbar
            if toolbar is None:
                return

            # The V0.6 toolbar order was Language -> spacer -> Help.
            # Keep the original widgets alive, hide the old spacer/help, and
            # insert a new expanding spacer before Language so the selector
            # occupies the former Help-button position on the right.
            for action in toolbar.actions():
                widget = toolbar.widgetForAction(action)
                if widget is None:
                    continue
                if widget not in (self.release_language_label, self.language_combo, self.help_button):
                    widget.hide()
            self.help_button.hide()

            spacer = QtWidgets.QWidget()
            spacer.setObjectName("v07LanguageToolbarSpacer")
            spacer.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Preferred,
            )
            actions = toolbar.actions()
            if actions:
                toolbar.insertWidget(actions[0], spacer)
            else:
                toolbar.addWidget(spacer)
            self._v07_toolbar_spacer = spacer

            self.release_language_label.setMinimumWidth(44)
            self.language_combo.setMinimumWidth(160)
            self.help_button.setVisible(False)

        def _configure_v07_response_overview(self):
            controller = getattr(self, "dynamic_pages", None)
            if controller is None:
                return

            row_widget = QtWidgets.QWidget(controller.response_page)
            row = QtWidgets.QHBoxLayout(row_widget)
            row.setContentsMargins(0, 0, 0, 0)
            label = QtWidgets.QLabel(row_widget)
            mode = QtWidgets.QComboBox(row_widget)
            mode.addItem("", "detail")
            mode.addItem("", "overview")
            mode.setMinimumWidth(230)
            row.addWidget(label)
            row.addWidget(mode)
            row.addSpacing(14)

            self.response_zoom_in_button = QtWidgets.QPushButton(row_widget)
            self.response_zoom_out_button = QtWidgets.QPushButton(row_widget)
            self.response_box_zoom_button = QtWidgets.QPushButton(row_widget)
            self.response_pan_button = QtWidgets.QPushButton(row_widget)
            self.response_reset_button = QtWidgets.QPushButton(row_widget)
            for button in (
                self.response_zoom_in_button,
                self.response_zoom_out_button,
                self.response_box_zoom_button,
                self.response_pan_button,
                self.response_reset_button,
            ):
                button.setMinimumHeight(28)
                row.addWidget(button)

            self.response_box_zoom_button.setCheckable(True)
            self.response_pan_button.setCheckable(True)
            self.response_pan_button.setChecked(True)
            self.response_zoom_in_button.clicked.connect(lambda: self._zoom_response_v07(0.80))
            self.response_zoom_out_button.clicked.connect(lambda: self._zoom_response_v07(1.25))
            self.response_box_zoom_button.clicked.connect(lambda: self._set_response_mouse_mode_v07("rect"))
            self.response_pan_button.clicked.connect(lambda: self._set_response_mouse_mode_v07("pan"))
            self.response_reset_button.clicked.connect(self._reset_response_view_v07)

            row.addStretch(1)

            root = controller.response_page.layout()
            root.insertWidget(2, row_widget)
            self.response_view_label = label
            self.response_view_mode = mode

            self._v07_response_base_refresh = controller.refresh_response_plot
            try:
                controller.response_event_combo.currentIndexChanged.disconnect()
            except (TypeError, RuntimeError):
                pass
            controller.response_event_combo.currentIndexChanged.connect(self._refresh_response_v07)
            mode.currentIndexChanged.connect(self._refresh_response_v07)
            # Internal controller calls (analysis/background refresh) now honor the selected view.
            controller.refresh_response_plot = self._refresh_response_v07

        def _response_plot_items_v07(self):
            return [plot for plot in self._response_plots_v07 if plot is not None]

        def _capture_response_ranges_v07(self):
            self._response_initial_ranges_v07 = []
            for plot in self._response_plot_items_v07():
                view = plot.viewRange()
                self._response_initial_ranges_v07.append(
                    (
                        (float(view[0][0]), float(view[0][1])),
                        (float(view[1][0]), float(view[1][1])),
                    )
                )
                plot.getViewBox().disableAutoRange()

        def _zoom_response_v07(self, factor: float):
            plots = self._response_plot_items_v07()
            if not plots:
                return
            # X axes are linked. Scale X only once, then scale each Y axis independently.
            plots[0].getViewBox().scaleBy(x=float(factor), y=1.0)
            for plot in plots:
                plot.getViewBox().scaleBy(x=1.0, y=float(factor))

        def _set_response_mouse_mode_v07(self, mode: str):
            controller = getattr(self, "dynamic_pages", None)
            if controller is None:
                return
            self._response_mouse_mode_v07 = mode
            mouse_mode = controller.pg.ViewBox.RectMode if mode == "rect" else controller.pg.ViewBox.PanMode
            for plot in self._response_plot_items_v07():
                plot.getViewBox().setMouseMode(mouse_mode)
            if self.response_box_zoom_button is not None:
                self.response_box_zoom_button.setChecked(mode == "rect")
            if self.response_pan_button is not None:
                self.response_pan_button.setChecked(mode == "pan")

        def _reset_response_view_v07(self):
            plots = self._response_plot_items_v07()
            if not plots or len(plots) != len(self._response_initial_ranges_v07):
                return
            first_x = self._response_initial_ranges_v07[0][0]
            plots[0].getViewBox().setRange(xRange=first_x, padding=0)
            for plot, (_x_range, y_range) in zip(plots, self._response_initial_ranges_v07):
                plot.getViewBox().setRange(yRange=y_range, padding=0)

        def _refresh_response_v07(self, *_args):
            if self.response_view_mode is not None and self.response_view_mode.currentData() == "overview":
                self._draw_response_overview()
            else:
                self._draw_response_detail_v07()

        @staticmethod
        def _finite_range(values, include=(), padding: float = 0.08):
            array = np.asarray(values, dtype=float)
            array = array[np.isfinite(array)]
            extras = np.asarray(list(include), dtype=float) if include else np.asarray([], dtype=float)
            extras = extras[np.isfinite(extras)]
            if extras.size:
                array = np.concatenate((array, extras)) if array.size else extras
            if not array.size:
                return (-1.0, 1.0)
            lo = float(np.nanmin(array))
            hi = float(np.nanmax(array))
            if np.isclose(lo, hi):
                span = max(abs(lo) * 0.1, 1.0)
            else:
                span = hi - lo
            return (lo - padding * span, hi + padding * span)

        @staticmethod
        def _first_progress_time(t, signal, start_value: float, end_value: float, after_time: float, fraction: float = 0.995):
            t = np.asarray(t, dtype=float)
            signal = np.asarray(signal, dtype=float)
            delta = float(end_value - start_value)
            mask = np.isfinite(t) & np.isfinite(signal) & (t >= float(after_time))
            if not mask.any():
                return float("nan")
            tt = t[mask]
            yy = signal[mask]
            if abs(delta) < 1e-12:
                return float(tt[0])
            progress = (yy - float(start_value)) / delta
            reached = np.flatnonzero(progress >= float(fraction))
            if reached.size:
                return float(tt[int(reached[0])])
            nearest = int(np.nanargmin(np.abs(progress - float(fraction))))
            return float(tt[nearest])

        def _marker_pen_v07(self):
            controller = self.dynamic_pages
            return controller.pg.mkPen(
                self._v07_response_marker_color,
                width=0.85,
                style=controller.QtCore.Qt.PenStyle.DashLine,
            )

        def _text_item_v07(self, text: str, x: float, y: float, anchor=(0, 1)):
            controller = self.dynamic_pages
            item = controller.pg.TextItem(anchor=anchor)
            item.setHtml(
                f"<div style='font-size:10pt;font-weight:400;color:{self._v07_response_marker_color};"
                f"background-color:rgba(255,255,255,0);'>{text}</div>"
            )
            item.setPos(float(x), float(y))
            return item

        def _add_marker_segment_v07(self, plot, x1: float, y1: float, x2: float, y2: float):
            return plot.plot(
                [float(x1), float(x2)],
                [float(y1), float(y2)],
                pen=self._marker_pen_v07(),
            )

        def _add_intersection_v07(self, plot, x: float, y: float, label: str | None = None, anchor=(0, 1)):
            if not np.isfinite(x) or not np.isfinite(y):
                return
            controller = self.dynamic_pages
            plot.plot(
                [float(x)],
                [float(y)],
                pen=None,
                symbol="o",
                symbolSize=7,
                symbolPen=controller.pg.mkPen(self._v07_response_marker_color, width=1.0),
                symbolBrush=controller.pg.mkBrush(self._v07_response_marker_color),
            )
            if label:
                plot.addItem(self._text_item_v07(label, float(x), float(y), anchor=anchor))

        def _add_horizontal_to_intersection_v07(self, plot, x_left: float, x_point: float, y: float, label: str):
            if not (np.isfinite(x_left) and np.isfinite(x_point) and np.isfinite(y)):
                return
            self._add_marker_segment_v07(plot, x_left, y, x_point, y)
            label_x = float(x_left + 0.01 * max(x_point - x_left, 1e-9))
            plot.addItem(self._text_item_v07(label, label_x, y, anchor=(0, 1)))

        def _add_vertical_to_intersection_v07(self, plot, x: float, y_from: float, y_point: float, label: str | None = None):
            if not (np.isfinite(x) and np.isfinite(y_from) and np.isfinite(y_point)):
                return
            self._add_marker_segment_v07(plot, x, y_from, x, y_point)
            if label:
                anchor = (0, 1) if y_point >= y_from else (0, 0)
                plot.addItem(self._text_item_v07(label, x, y_point, anchor=anchor))

        def _draw_response_detail_v07(self):
            controller = getattr(self, "dynamic_pages", None)
            if controller is None or controller.response_result is None or controller.response_result.events.empty:
                if self._v07_response_base_refresh is not None:
                    self._v07_response_base_refresh()
                return

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
                return
            full_data = full_data.sort_values(TIME)

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
            response_end_candidates = [value for value in (t90, f100_time, i100_time, t0 + 0.020) if np.isfinite(value)]
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
            velocity = data[VELOCITY].to_numpy(float) if VELOCITY in data.columns else np.gradient(displacement, t) / 1000.0

            controller.response_plot_area.clear()
            stage = controller._display_value("Stage", row["Stage"])
            direction = controller._display_value("Direction", row["Direction"])
            is_bmw = str(row.get("OEM", "")).upper() == "BMW" or str(controller.response_standard.currentData()).lower() == "bmw"

            plots = []
            if is_bmw:
                displacement_plot = controller.response_plot_area.addPlot(row=0, col=0)
                displacement_plot.setTitle(
                    self._text_v07(f"位移｜{stage}｜{direction}", f"Displacement | {row['Stage']} | {row['Direction']}"),
                    size="11pt",
                )
                controller._axis_style(displacement_plot, self._text_v07("位移", "Displacement"), "mm")
                displacement_plot.plot(t, displacement, pen=controller._curve_pen(1.6))

                current_plot = controller.response_plot_area.addPlot(row=1, col=0)
                current_plot.setXLink(displacement_plot)
                current_plot.setTitle(self._text_v07("电流", "Current"), size="11pt")
                controller._axis_style(current_plot, self._text_v07("阀电流", "Valve current"), "A")
                current_plot.plot(t, current, pen=controller._curve_pen(1.6))

                force_plot = controller.response_plot_area.addPlot(row=2, col=0)
                force_plot.setXLink(displacement_plot)
                force_plot.setTitle(self._text_v07("阻尼力", "Damping Force"), size="11pt")
                controller._axis_style(force_plot, self._text_v07("阻尼力", "Damping force"), "N")
                force_plot.plot(t, force, pen=controller._curve_pen(1.7))
                plots = [displacement_plot, current_plot, force_plot]
            else:
                current_plot = controller.response_plot_area.addPlot(row=0, col=0)
                current_plot.setTitle(
                    self._text_v07(f"电流响应｜{stage}｜{direction}", f"Current Response | {row['Stage']} | {row['Direction']}"),
                    size="11pt",
                )
                controller._axis_style(current_plot, self._text_v07("阀电流", "Valve current"), "A")
                current_plot.plot(t, current, pen=controller._curve_pen(1.6))

                force_plot = controller.response_plot_area.addPlot(row=1, col=0)
                force_plot.setXLink(current_plot)
                force_plot.setTitle(self._text_v07("阻尼力响应", "Damping Force Response"), size="11pt")
                controller._axis_style(force_plot, self._text_v07("阻尼力", "Damping force"), "N")
                force_plot.plot(t, force, pen=controller._curve_pen(1.7))

                velocity_plot = controller.response_plot_area.addPlot(row=2, col=0)
                velocity_plot.setXLink(current_plot)
                velocity_plot.setTitle(self._text_v07("速度", "Velocity"), size="11pt")
                controller._axis_style(velocity_plot, self._text_v07("速度", "Velocity"), "m/s")
                velocity_plot.plot(t, velocity, pen=controller._curve_pen(1.5))
                plots = [current_plot, force_plot, velocity_plot]

            for plot in plots:
                plot.setMinimumHeight(225)

            # Current markers: thin blue dashed segments. Horizontal lines stop at their intersection.
            trigger_current = float(row["Trigger Current A"])
            start_current = float(row["Current Start A"])
            end_current = float(row["Current End A"])
            current_left = detail_start
            self._add_horizontal_to_intersection_v07(current_plot, current_left, t0, trigger_current, "I10% / 10%")
            self._add_vertical_to_intersection_v07(current_plot, t0, start_current, trigger_current, "t0")
            self._add_intersection_v07(current_plot, t0, trigger_current)
            if np.isfinite(i100_time):
                self._add_horizontal_to_intersection_v07(current_plot, current_left, i100_time, end_current, "I100% / 100%")
                self._add_intersection_v07(current_plot, i100_time, end_current)

            # Force markers: both horizontal and vertical evaluation lines terminate exactly at the point.
            threshold_specs = (
                ("F1 N", "t1 s", "F1%", "t1%"),
                ("F10 N", "t10 s", "F10%", "t10%"),
                ("F63 N", "t63 s", "F63%", "t63%"),
                ("F90 N", "t90 s", "F90%", "t90%"),
            )
            force_left = detail_start
            f0 = float(row["F0 N"])
            self._add_horizontal_to_intersection_v07(force_plot, force_left, t0, f0, "F0")
            self._add_intersection_v07(force_plot, t0, f0)
            for force_key, time_key, force_label, time_label in threshold_specs:
                force_value = float(row.get(force_key, np.nan))
                time_value = float(row.get(time_key, np.nan))
                if not (np.isfinite(force_value) and np.isfinite(time_value)):
                    continue
                self._add_horizontal_to_intersection_v07(force_plot, force_left, time_value, force_value, force_label)
                # The vertical line starts at the X axis (F=0) and stops at the intersection.
                self._add_vertical_to_intersection_v07(force_plot, time_value, 0.0, force_value, time_label)
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
            y_label = float(np.nanmax(force)) if row["Direction"] == "Rebound" else float(np.nanmin(force))
            force_plot.addItem(self._text_item_v07(direction_text, detail_start + 0.02 * (detail_end - detail_start), y_label, anchor=(0, 1)))

            if not is_bmw:
                target_velocity = float(row.get("Target Velocity m/s", np.nan))
                if np.isfinite(target_velocity):
                    self._add_marker_segment_v07(velocity_plot, detail_start, target_velocity, detail_end, target_velocity)
                    velocity_plot.addItem(
                        self._text_item_v07(
                            self._text_v07(f"目标速度 {target_velocity:.4f} m/s", f"Target {target_velocity:.4f} m/s"),
                            detail_start + 0.01 * (detail_end - detail_start),
                            target_velocity,
                            anchor=(0, 1),
                        )
                    )

            # Stable, deterministic initial ranges make one-click Reset reliable after any zoom/pan action.
            for plot in plots:
                plot.getViewBox().disableAutoRange()
            x_range = (float(detail_start), float(detail_end))
            if is_bmw:
                disp_range = self._finite_range(displacement)
                current_range = self._finite_range(current, include=(start_current, trigger_current, end_current))
                force_range = self._finite_range(
                    force,
                    include=(0.0, f0, row.get("F1 N", np.nan), row.get("F10 N", np.nan), row.get("F63 N", np.nan), row.get("F90 N", np.nan), row.get("F100 N", np.nan)),
                )
                displacement_plot.getViewBox().setRange(xRange=x_range, yRange=disp_range, padding=0)
                current_plot.getViewBox().setRange(yRange=current_range, padding=0)
                force_plot.getViewBox().setRange(yRange=force_range, padding=0)
            else:
                current_range = self._finite_range(current, include=(start_current, trigger_current, end_current))
                force_range = self._finite_range(
                    force,
                    include=(0.0, f0, row.get("F1 N", np.nan), row.get("F10 N", np.nan), row.get("F63 N", np.nan), row.get("F90 N", np.nan), row.get("F100 N", np.nan)),
                )
                velocity_range = self._finite_range(velocity, include=(row.get("Target Velocity m/s", np.nan),))
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
            data = controller.response_result.processed.copy()
            if data.empty:
                return
            data = data.sort_values(TIME)
            plot_area = controller.response_plot_area
            plot_area.clear()
            t = data[TIME].to_numpy(float)

            specifications = (
                (LOAD, self._text_v07("阻尼力（复原 + / 压缩 -）", "Damping force (Rebound + / Compression -)"), "N"),
                (CURRENT, self._text_v07("阀电流", "Valve current"), "A"),
                (DISP, self._text_v07("位移", "Displacement"), "mm"),
            )
            previous = None
            plots = []
            for row_index, (column, label, unit) in enumerate(specifications):
                plot = plot_area.addPlot(row=row_index, col=0)
                controller._axis_style(plot, label, unit)
                plot.setMinimumHeight(225)
                plot.plot(t, data[column].to_numpy(float), pen=controller._curve_pen(1.5))
                if previous is not None:
                    plot.setXLink(previous)
                previous = plot
                plots.append(plot)

            plots[0].setTitle(
                self._text_v07("响应时间试验全流程总览（Audi 图15风格）", "Full response-test overview (Audi Fig. 15 style)"),
                size="12pt",
            )

            events = controller.response_result.events
            if not events.empty:
                force_values = data[LOAD].to_numpy(float)
                current_values = data[CURRENT].to_numpy(float)
                force_top = float(np.nanmax(force_values)) if len(force_values) else 0.0
                current_top = float(np.nanmax(current_values)) if len(current_values) else 0.0
                for _, event in events.iterrows():
                    event_time = float(event.get("t0 s", np.nan))
                    if not np.isfinite(event_time):
                        continue
                    for plot in plots:
                        controller._add_vertical_marker(plot, event_time)
                    stage = controller._display_value("Stage", event.get("Stage", ""))
                    direction = controller._display_value("Direction", event.get("Direction", ""))
                    event_id = int(event.get("Event ID", 0))
                    controller._add_intersection(
                        plots[1],
                        event_time,
                        float(event.get("Trigger Current A", current_top)),
                        f"E{event_id}",
                    )
                    plots[0].addItem(
                        controller._text_item(
                            f"E{event_id}  {stage}  {direction}",
                            event_time,
                            force_top,
                            anchor=(0, 0),
                        )
                    )

            self._response_plots_v07 = plots
            for plot in plots:
                plot.enableAutoRange(x=True, y=True)
                plot.autoRange()
            self._capture_response_ranges_v07()
            self._set_response_mouse_mode_v07(self._response_mouse_mode_v07)

        def _text_v07(self, zh: str, en: str) -> str:
            return zh if self.language == "zh_CN" else en

        def _apply_v05_language(self):
            super()._apply_v05_language()
            if getattr(self, "_v07_ready", False):
                self._apply_v07_language()

        def _apply_v07_language(self):
            if self.release_language_label is not None:
                self.release_language_label.setText("语言" if self.language == "zh_CN" else "Language")
            self.help_button.setVisible(False)
            help_index = self.tabs.indexOf(self.help_page)
            if help_index >= 0:
                self.tabs.setTabText(help_index, "帮助" if self.language == "zh_CN" else "Help")
            self.help_browser.setHtml(_help_html_v07(self.language))

            if self.response_view_label is not None and self.response_view_mode is not None:
                self.response_view_label.setText("图形视图" if self.language == "zh_CN" else "Plot view")
                self.response_view_mode.setItemText(
                    self.response_view_mode.findData("detail"),
                    "阶段详情" if self.language == "zh_CN" else "Event detail",
                )
                self.response_view_mode.setItemText(
                    self.response_view_mode.findData("overview"),
                    "全流程总览（Audi图15）" if self.language == "zh_CN" else "Full overview (Audi Fig. 15)",
                )
            if self.response_zoom_in_button is not None:
                self.response_zoom_in_button.setText("放大" if self.language == "zh_CN" else "Zoom in")
                self.response_zoom_out_button.setText("缩小" if self.language == "zh_CN" else "Zoom out")
                self.response_box_zoom_button.setText("框选放大" if self.language == "zh_CN" else "Box zoom")
                self.response_pan_button.setText("平移" if self.language == "zh_CN" else "Pan")
                self.response_reset_button.setText("恢复" if self.language == "zh_CN" else "Reset")
            self._refresh_response_v07()

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
