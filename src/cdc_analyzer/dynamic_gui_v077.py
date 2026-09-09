from __future__ import annotations

import numpy as np

from .dynamic_analysis import CURRENT, LOAD, TIME, VELOCITY
from .dynamic_gui_v076 import DynamicPagesController as _V076DynamicPagesController


class DynamicPagesController(_V076DynamicPagesController):
    """V0.7.7 response-plot presentation refinements.

    The response calculation itself is unchanged. This layer only adjusts the
    detail-plot presentation requested during visual validation:
    - response detail time axis is shown directly in seconds;
    - reference dashes use a wider dash/gap pattern;
    - the force-direction annotation is removed from the force plot;
    - the target-velocity line/text is removed from the velocity plot.
    """

    def _axis_style(self, plot, left: str, units: str | None = None):
        plot.showGrid(x=True, y=False, alpha=0.12)
        label_style = {"font-size": "11pt"}
        plot.setLabel("left", left, units=units, **label_style)
        # Use seconds directly. Passing millisecond-valued X data together with
        # units="ms" allowed pyqtgraph SI-prefix scaling to display "kms".
        plot.setLabel(
            "bottom",
            self._text("时间", "Time"),
            units="s",
            **label_style,
        )
        plot.setClipToView(True)
        plot.setDownsampling(auto=True, mode="peak")
        background = getattr(self.window, "_plot_background_color", "#ffffff")
        foreground = getattr(self.window, "_plot_foreground_color", "#202020")
        plot.getAxis("left").setTextPen(foreground)
        plot.getAxis("bottom").setTextPen(foreground)
        tick_font = self.QtWidgets.QApplication.font()
        tick_font.setPointSize(max(10, tick_font.pointSize()))
        plot.getAxis("left").setStyle(tickFont=tick_font)
        plot.getAxis("bottom").setStyle(tickFont=tick_font)
        self.response_plot_area.setBackground(background)
        self.hysteresis_plot_area.setBackground(background)

    def _marker_pen(self):
        foreground = getattr(self.window, "_plot_foreground_color", "#202020")
        pen = self.pg.mkPen(foreground, width=1.0)
        pen.setStyle(self.QtCore.Qt.PenStyle.CustomDashLine)
        # Qt dash units are multiples of pen width. A 12/8 pattern leaves
        # noticeably larger gaps than the default DashLine pattern while
        # keeping the reference lines light.
        pen.setDashPattern([12.0, 8.0])
        return pen

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
        data = self.response_result.processed[
            self.response_result.processed[TIME].between(start, end)
        ]
        if data.empty:
            return

        # Plot the measured running time directly in seconds so the engineering
        # reading is 1.100, 1.110, ... s instead of an SI-prefixed "kms" axis.
        t_s = data[TIME].to_numpy(float)
        t0_s = float(row["t0 s"])
        x_left = float(t_s[0])
        x_right = float(t_s[-1])
        x_label = x_left + 0.02 * max(x_right - x_left, 1e-9)
        marker_pen = self._marker_pen()
        signal_pen = self._signal_pen()

        current_plot = self.response_plot_area.addPlot(row=0, col=0)
        self._axis_style(current_plot, self._text("阀电流", "Valve current"), "A")
        current_plot.plot(t_s, data[CURRENT].to_numpy(float), pen=signal_pen)
        current_plot.addLine(x=t0_s, pen=marker_pen)
        current_levels = (
            ("I10%", float(row["Trigger Current A"])),
            ("I100%", float(row["Current 100% A"])),
        )
        for label, value in current_levels:
            current_plot.addLine(y=value, pen=marker_pen)
            self._add_plot_text(current_plot, label, x_label, value)
        current_plot.setTitle(
            self._text(
                f"电流｜{row.get('Stage', '')}｜{row['Direction']}",
                f"Current | {row.get('Stage', '')} | {row['Direction']}",
            )
        )

        force_plot = self.response_plot_area.addPlot(row=1, col=0)
        force_plot.setXLink(current_plot)
        self._axis_style(force_plot, self._text("阻尼力", "Damping force"), "kN")
        force_kn = data[LOAD].to_numpy(float) / 1000.0
        force_plot.plot(t_s, force_kn, pen=signal_pen)
        force_plot.addLine(x=t0_s, pen=marker_pen)

        force_levels = (
            ("1%", float(row["F1 N"]) / 1000.0),
            ("63%", float(row["F63 N"]) / 1000.0),
            ("90%", float(row["F90 N"]) / 1000.0),
            ("100%", float(row["F100 N"]) / 1000.0),
        )
        for label, value in force_levels:
            force_plot.addLine(y=value, pen=marker_pen)
            self._add_plot_text(force_plot, label, x_label, value)

        response_markers = (
            ("t1", float(row["Dead Time t1 ms"])),
            ("t63", float(row["Switch Time t63 ms"])),
            ("t90", float(row["Switch Time t90 ms"])),
        )
        finite_marker_positions: list[tuple[str, float]] = []
        for label, elapsed_ms in response_markers:
            if np.isfinite(elapsed_ms):
                x_value = t0_s + elapsed_ms / 1000.0
                force_plot.addLine(x=x_value, pen=marker_pen)
                finite_marker_positions.append((label, x_value))
        if len(force_kn):
            y_min = float(np.nanmin(force_kn))
            y_max = float(np.nanmax(force_kn))
            y_span = max(y_max - y_min, 0.1)
            for index, (label, x_value) in enumerate(finite_marker_positions):
                y = y_max - (0.08 + 0.12 * index) * y_span
                self._add_plot_text(
                    force_plot,
                    label,
                    x_value,
                    y,
                    anchor=(0.5, 0.5),
                )

        # Direction (Rebound/Compression) remains available in the event title,
        # selector and result table. Do not repeat "复原（+）/压缩（-）" inside
        # the force plot itself.

        velocity_plot = self.response_plot_area.addPlot(row=2, col=0)
        velocity_plot.setXLink(current_plot)
        self._axis_style(velocity_plot, self._text("速度", "Velocity"), "m/s")
        velocity_plot.plot(t_s, data[VELOCITY].to_numpy(float), pen=signal_pen)
        velocity_plot.addLine(x=t0_s, pen=marker_pen)
        # Target velocity is still used by the response-event gating and stays
        # in the result table, but its horizontal line/text are intentionally
        # omitted from the detail plot.

        current_plot.setXRange(x_left, x_right, padding=0.01)
