from __future__ import annotations

from .dynamic_gui_v077 import DynamicPagesController as _V077DynamicPagesController


class DynamicPagesController(_V077DynamicPagesController):
    """V0.7.8 response presentation corrections.

    - Chinese UI localizes response stage/direction values instead of exposing
      internal English enum text.
    - The velocity detail plot shows the target-speed horizontal dashed line.
      The old t0 vertical line is removed from the velocity plot.
    - Target-speed text remains omitted to keep the velocity plot uncluttered.
    """

    def _localized_stage(self, value: object) -> str:
        text = str(value or "")
        if self.window.language != "zh_CN":
            return text
        replacements = (
            ("Soft", "软"),
            ("Hard", "硬"),
            ("Medium", "中间"),
            ("Mid", "中间"),
        )
        for source, target in replacements:
            text = text.replace(source, target)
        return text

    def _localized_direction(self, value: object, *, signed: bool = False) -> str:
        text = str(value or "")
        if self.window.language != "zh_CN":
            if not signed:
                return text
            if text == "Rebound":
                return "Rebound (+)"
            if text == "Compression":
                return "Compression (-)"
            return text
        if text == "Rebound":
            return "复原(+)" if signed else "复原"
        if text == "Compression":
            return "压缩(-)" if signed else "压缩"
        return text

    def _rebuild_response_event_combo(self) -> None:
        if self.response_result is None or self.response_result.events.empty:
            return
        current_event = self.response_event_combo.currentData()
        self.response_event_combo.blockSignals(True)
        self.response_event_combo.clear()
        for _, row in self.response_result.events.iterrows():
            stage = self._localized_stage(row.get("Stage", ""))
            direction = self._localized_direction(row.get("Direction", ""), signed=True)
            current_transition = str(row.get("Current Transition", ""))
            target = float(row["Target Velocity m/s"])
            if self.window.language == "zh_CN":
                text = f"{stage} | {direction} | {current_transition} | 目标速度 {target:+.4g} m/s"
            else:
                text = f"{stage} | {direction} | {current_transition} | Target {target:+.4g} m/s"
            self.response_event_combo.addItem(text, int(row["Event ID"]))
        restore_index = self.response_event_combo.findData(current_event)
        self.response_event_combo.setCurrentIndex(restore_index if restore_index >= 0 else 0)
        self.response_event_combo.blockSignals(False)

    def analyze_response(self):
        super().analyze_response()
        if self.response_result is not None and not self.response_result.events.empty:
            self._rebuild_response_event_combo()
            self._fill_table(self.response_table, self.response_result.events)
            self.refresh_response_plot()

    def apply_language(self, language: str):
        super().apply_language(language)
        if getattr(self, "response_result", None) is not None:
            self._rebuild_response_event_combo()
            self._fill_table(self.response_table, self.response_result.events)
            self.refresh_response_plot()

    def _fill_table(self, table, frame):
        super()._fill_table(table, frame)
        if (
            self.window.language != "zh_CN"
            or not hasattr(self, "response_table")
            or table is not self.response_table
        ):
            return
        columns = [str(column) for column in frame.columns]
        for column_name, translator in (
            ("Stage", self._localized_stage),
            ("Direction", self._localized_direction),
        ):
            if column_name not in columns:
                continue
            column_index = columns.index(column_name)
            for row_index in range(table.rowCount()):
                item = table.item(row_index, column_index)
                if item is not None:
                    item.setText(translator(item.text()))

    def refresh_response_plot(self):
        super().refresh_response_plot()
        if self.response_result is None or self.response_result.events.empty:
            return

        event_id = self.response_event_combo.currentData()
        if event_id is None:
            event_id = int(self.response_result.events["Event ID"].iloc[0])
        row = self.response_result.events[
            self.response_result.events["Event ID"] == event_id
        ].iloc[0]

        current_plot = self.response_plot_area.getItem(0, 0)
        velocity_plot = self.response_plot_area.getItem(2, 0)
        if current_plot is not None:
            stage = self._localized_stage(row.get("Stage", ""))
            direction = self._localized_direction(row.get("Direction", ""))
            current_plot.setTitle(
                self._text(
                    f"电流｜{stage}｜{direction}",
                    f"Current | {stage} | {direction}",
                )
            )

        if velocity_plot is not None:
            # V0.7.7 left a t0 vertical marker on the velocity subplot. For the
            # engineering view the useful reference here is target velocity,
            # so remove vertical reference lines and restore one horizontal
            # target-speed dashed line. Keep the target text hidden.
            for item in list(velocity_plot.items):
                if isinstance(item, self.pg.InfiniteLine):
                    velocity_plot.removeItem(item)
            target_velocity = float(row["Target Velocity m/s"])
            velocity_plot.addLine(y=target_velocity, pen=self._marker_pen())
