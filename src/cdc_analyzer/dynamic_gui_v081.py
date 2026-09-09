from __future__ import annotations

import numpy as np

from .dynamic_analysis import CURRENT, LOAD, TIME, VELOCITY
from .dynamic_gui_v080 import DynamicPagesController as _V080DynamicPagesController


class DynamicPagesController(_V080DynamicPagesController):
    """V0.8.1 engineering notation for response-detail plots.

    Presentation changes only:
    - current reference labels use engineering subscripts: I₁₀%, I₁₀₀%;
    - force reference labels use F with subscripted percentage levels;
    - response-time markers use t with subscripted percentage levels and show
      the calculated result directly beside the marker, e.g. t₉₀% = 7.21 ms;
    - all reference lines remain dashed; measured signals remain solid.
    """

    def _format_response_ms(self, value: float) -> str:
        return f"{value:.2f}"

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

        t_s = data[TIME].to_numpy(float)
        t0_s = float(row["t0 s"])
        x_left = float(t_s[0])
        x_right = float(t_s[-1])
        x_label = x_left + 0.02 * max(x_right - x_left, 1e-9)
        marker_pen = self._marker_pen()
        signal_pen = self._signal_pen()

        stage = self._localized_stage(row.get("Stage", ""))
        direction = self._localized_direction(row.get("Direction", ""))

        current_plot = self.response_plot_area.addPlot(row=0, col=0)
        self._axis_style(current_plot, self._text("阀电流", "Valve current"), "A")
        current_plot.plot(t_s, data[CURRENT].to_numpy(float), pen=signal_pen)
        current_plot.addLine(x=t0_s, pen=marker_pen)
        current_levels = (
            ("I₁₀%", float(row["Trigger Current A"])),
            ("I₁₀₀%", float(row["Current 100% A"])),
        )
        for label, value in current_levels:
            current_plot.addLine(y=value, pen=marker_pen)
            self._add_plot_text(current_plot, label, x_label, value)
        current_plot.setTitle(
            self._text(
                f"电流｜{stage}｜{direction}",
                f"Current | {stage} | {direction}",
            )
        )

        force_plot = self.response_plot_area.addPlot(row=1, col=0)
        force_plot.setXLink(current_plot)
        self._axis_style(force_plot, self._text("阻尼力", "Damping force"), "kN")
        force_kn = data[LOAD].to_numpy(float) / 1000.0
        force_plot.plot(t_s, force_kn, pen=signal_pen)
        force_plot.addLine(x=t0_s, pen=marker_pen)

        force_levels = (
            ("F₁%", float(row["F1 N"]) / 1000.0),
            ("F₆₃%", float(row["F63 N"]) / 1000.0),
            ("F₉₀%", float(row["F90 N"]) / 1000.0),
            ("F₁₀₀%", float(row["F100 N"]) / 1000.0),
        )
        for label, value in force_levels:
            force_plot.addLine(y=value, pen=marker_pen)
            self._add_plot_text(force_plot, label, x_label, value)

        response_markers = (
            ("t₁%", float(row["Dead Time t1 ms"])),
            ("t₆₃%", float(row["Switch Time t63 ms"])),
            ("t₉₀%", float(row["Switch Time t90 ms"])),
        )
        finite_marker_positions: list[tuple[str, float, float]] = []
        for label, elapsed_ms in response_markers:
            if np.isfinite(elapsed_ms):
                x_value = t0_s + elapsed_ms / 1000.0
                force_plot.addLine(x=x_value, pen=marker_pen)
                finite_marker_positions.append((label, x_value, elapsed_ms))

        if len(force_kn):
            y_min = float(np.nanmin(force_kn))
            y_max = float(np.nanmax(force_kn))
            y_span = max(y_max - y_min, 0.1)
            for index, (label, x_value, elapsed_ms) in enumerate(finite_marker_positions):
                y = y_max - (0.08 + 0.12 * index) * y_span
                result_text = f"{label} = {self._format_response_ms(elapsed_ms)} ms"
                self._add_plot_text(
                    force_plot,
                    result_text,
                    x_value,
                    y,
                    anchor=(0.5, 0.5),
                )

        velocity_plot = self.response_plot_area.addPlot(row=2, col=0)
        velocity_plot.setXLink(current_plot)
        self._axis_style(velocity_plot, self._text("速度", "Velocity"), "m/s")
        velocity_plot.plot(t_s, data[VELOCITY].to_numpy(float), pen=signal_pen)
        target_velocity = float(row["Target Velocity m/s"])
        velocity_plot.addLine(y=target_velocity, pen=marker_pen)

        current_plot.setXRange(x_left, x_right, padding=0.01)
