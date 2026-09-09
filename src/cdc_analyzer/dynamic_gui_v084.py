from __future__ import annotations

import numpy as np

from .dynamic_analysis import CURRENT, LOAD, TIME, VELOCITY
from .dynamic_gui_v083 import DynamicPagesController as _V083DynamicPagesController


class DynamicPagesController(_V083DynamicPagesController):
    """V0.8.4 response plots with transparent labels and curve-intersection markers."""

    def _axis_title_font(self, plot):
        """Return a normal-weight font matching the plot's left-axis title font."""
        axis = plot.getAxis("left")
        label_item = getattr(axis, "label", None)
        font = label_item.font() if label_item is not None else self.QtWidgets.QApplication.font()
        font.setBold(False)
        return font

    def _add_response_text(self, plot, text, x, y, *, anchor=(0, 1), bold=False):
        foreground = getattr(self.window, "_plot_foreground_color", "#202020")
        # Deliberately omit fill/background: engineering annotations remain transparent.
        item = self.pg.TextItem(
            text=text,
            color=foreground,
            anchor=anchor,
            fill=None,
        )
        font = self._axis_title_font(plot)
        font.setBold(False)
        item.setFont(font)
        item.setPos(float(x), float(y))
        item.setZValue(30)
        plot.addItem(item)
        return item

    @staticmethod
    def _curve_y_at(x_values, y_values, x_value: float) -> float:
        x = np.asarray(x_values, dtype=float)
        y = np.asarray(y_values, dtype=float)
        finite = np.isfinite(x) & np.isfinite(y)
        if finite.sum() < 2:
            return float("nan")
        x = x[finite]
        y = y[finite]
        order = np.argsort(x, kind="stable")
        x = x[order]
        y = y[order]
        if x_value < x[0] or x_value > x[-1]:
            return float("nan")
        return float(np.interp(float(x_value), x, y))

    def _add_curve_intersection_marker(self, plot, x_value: float, y_value: float):
        if not (np.isfinite(x_value) and np.isfinite(y_value)):
            return None
        foreground = getattr(self.window, "_plot_foreground_color", "#202020")
        marker = self.pg.ScatterPlotItem(
            x=[float(x_value)],
            y=[float(y_value)],
            symbol="o",
            size=8,
            pen=self.pg.mkPen(foreground, width=1.2),
            brush=self.pg.mkBrush(foreground),
        )
        marker.setZValue(25)
        plot.addItem(marker)
        return marker

    @staticmethod
    def _vertical_text_position(y_value: float, y_min: float, y_max: float, index: int = 0):
        y_span = max(float(y_max) - float(y_min), 1e-9)
        offset = max(0.055 * y_span, 1e-6)
        near_top = y_value >= y_max - 0.15 * y_span
        near_bottom = y_value <= y_min + 0.15 * y_span
        if near_top:
            above = False
        elif near_bottom:
            above = True
        else:
            above = index % 2 == 0
        if above:
            return float(y_value + offset), (0.5, 1.0)
        return float(y_value - offset), (0.5, 0.0)

    def refresh_response_plot(self):
        self.response_plot_area.clear()
        if self.response_result is None or self.response_result.events.empty:
            return

        event_id = self.response_event_combo.currentData()
        if event_id is None:
            event_id = int(self.response_result.events["Event ID"].iloc[0])
        row = self.response_result.events[
            self.response_result.events["Event ID"] == event_id
        ].iloc[0]
        self._sync_response_table_selection(int(event_id))

        start = float(row.get("Display Start s", row["Segment Start s"]))
        end = float(row.get("Display End s", row["Segment End s"]))
        # Keep the complete target-speed endpoint window visible so F100 remains traceable.
        end = max(end, float(row.get("Target Window End s", end)))
        data = self.response_result.processed[
            self.response_result.processed[TIME].between(start, end)
        ]
        if data.empty:
            return

        t_s = data[TIME].to_numpy(float)
        current_a = data[CURRENT].to_numpy(float)
        force_kn = data[LOAD].to_numpy(float) / 1000.0
        velocity = data[VELOCITY].to_numpy(float)
        t0_s = float(row["t0 s"])
        x_left = float(t_s[0])
        x_right = float(t_s[-1])
        x_span = max(x_right - x_left, 1e-9)
        x_label = x_left + 0.02 * x_span
        marker_pen = self._marker_pen()
        signal_pen = self._signal_pen()

        stage = self._localized_stage(row.get("Stage", ""))
        direction = self._localized_direction(row.get("Direction", ""))

        current_plot = self.response_plot_area.addPlot(row=0, col=0)
        self._axis_style(current_plot, self._text("阀电流", "Valve current"), "A")
        current_plot.plot(t_s, current_a, pen=signal_pen)
        current_plot.addLine(x=t0_s, pen=marker_pen)
        for label, value in (
            ("I₁₀%", float(row["Trigger Current A"])),
            ("I₁₀₀%", float(row["Current 100% A"])),
        ):
            current_plot.addLine(y=value, pen=marker_pen)
            self._add_response_text(current_plot, label, x_label, value, anchor=(0, 1))

        current_t0_y = self._curve_y_at(t_s, current_a, t0_s)
        self._add_curve_intersection_marker(current_plot, t0_s, current_t0_y)
        if np.isfinite(current_t0_y):
            current_min = float(np.nanmin(current_a))
            current_max = float(np.nanmax(current_a))
            text_y, anchor = self._vertical_text_position(current_t0_y, current_min, current_max, 0)
            self._add_response_text(current_plot, "t₀", t0_s, text_y, anchor=anchor)

        current_plot.setTitle(
            self._text(
                f"电流｜{stage}｜{direction}",
                f"Current | {stage} | {direction}",
            )
        )

        force_plot = self.response_plot_area.addPlot(row=1, col=0)
        force_plot.setXLink(current_plot)
        self._axis_style(force_plot, self._text("阻尼力", "Damping force"), "kN")
        force_plot.plot(t_s, force_kn, pen=signal_pen)
        force_plot.addLine(x=t0_s, pen=marker_pen)

        for label, value in (
            ("F₁%", float(row["F1 N"]) / 1000.0),
            ("F₆₃%", float(row["F63 N"]) / 1000.0),
            ("F₉₀%", float(row["F90 N"]) / 1000.0),
            ("F₁₀₀%", float(row["F100 N"]) / 1000.0),
        ):
            force_plot.addLine(y=value, pen=marker_pen)
            self._add_response_text(force_plot, label, x_label, value, anchor=(0, 1))

        vertical_markers = [("t₀", t0_s, None)]
        for label, elapsed_ms in (
            ("t₁%", float(row["Dead Time t1 ms"])),
            ("t₆₃%", float(row["Switch Time t63 ms"])),
            ("t₉₀%", float(row["Switch Time t90 ms"])),
        ):
            if np.isfinite(elapsed_ms):
                x_value = t0_s + elapsed_ms / 1000.0
                force_plot.addLine(x=x_value, pen=marker_pen)
                vertical_markers.append((label, x_value, elapsed_ms))

        if len(force_kn):
            y_min = float(np.nanmin(force_kn))
            y_max = float(np.nanmax(force_kn))
            for index, (label, x_value, elapsed_ms) in enumerate(vertical_markers):
                y_value = self._curve_y_at(t_s, force_kn, x_value)
                self._add_curve_intersection_marker(force_plot, x_value, y_value)
                if not np.isfinite(y_value):
                    continue
                text_y, anchor = self._vertical_text_position(y_value, y_min, y_max, index)
                text = label if elapsed_ms is None else f"{label} = {self._format_response_ms(elapsed_ms)} ms"
                # The label shares the marker x-coordinate and moves only vertically.
                self._add_response_text(force_plot, text, x_value, text_y, anchor=anchor)

        velocity_plot = self.response_plot_area.addPlot(row=2, col=0)
        velocity_plot.setXLink(current_plot)
        self._axis_style(velocity_plot, self._text("速度", "Velocity"), "m/s")
        velocity_plot.plot(t_s, velocity, pen=signal_pen)
        velocity_plot.addLine(y=float(row["Target Velocity m/s"]), pen=marker_pen)

        current_plot.setXRange(x_left, x_right, padding=0.01)
