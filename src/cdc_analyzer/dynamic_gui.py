from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .dynamic_analysis import (
    CURRENT,
    DISP,
    LOAD,
    TIME,
    VELOCITY,
    HysteresisConfig,
    HysteresisStandard,
    ResponseConfig,
    ResponseStandard,
    analyze_hysteresis,
    analyze_response_time,
    load_dynamic_test_data,
)
from .dynamic_export import export_hysteresis_xlsx, export_response_xlsx
from .formatting import format_value


TABLE_STYLE = """
QTableWidget::item:hover {
    background-color: #e8f5e9;
    color: #202020;
}
QTableWidget::item:selected {
    background-color: #dff2df;
    color: #202020;
}
QTableWidget::item:selected:hover {
    background-color: #cfe8cf;
    color: #202020;
}
"""


class DynamicPagesController:
    def __init__(self, window, QtCore, QtWidgets, pg):
        self.window = window
        self.QtCore = QtCore
        self.QtWidgets = QtWidgets
        self.pg = pg
        self.response_dataset = None
        self.response_result = None
        self.response_path: Path | None = None
        self.hysteresis_dataset = None
        self.hysteresis_result = None
        self.hysteresis_path: Path | None = None
        self._build_response_page()
        self._build_hysteresis_page()
        self.apply_language(window.language)

    def _text(self, zh: str, en: str) -> str:
        return zh if self.window.language == "zh_CN" else en

    def _new_table(self):
        table = self.QtWidgets.QTableWidget()
        table.setAlternatingRowColors(True)
        table.setMouseTracking(True)
        table.viewport().setMouseTracking(True)
        table.setStyleSheet(TABLE_STYLE)
        table.setSelectionBehavior(self.QtWidgets.QAbstractItemView.SelectionBehavior.SelectItems)
        table.setSelectionMode(self.QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(self.QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(self.QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        return table

    def _build_response_page(self):
        self.response_page = self.QtWidgets.QWidget()
        root = self.QtWidgets.QVBoxLayout(self.response_page)

        controls = self.QtWidgets.QHBoxLayout()
        self.response_open_button = self.QtWidgets.QPushButton()
        self.response_open_button.clicked.connect(self.open_response_file)
        controls.addWidget(self.response_open_button)
        self.response_file_label = self.QtWidgets.QLabel()
        self.response_file_label.setMinimumWidth(220)
        self.response_file_label.setTextInteractionFlags(self.QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        controls.addWidget(self.response_file_label, 1)

        self.response_standard_label = self.QtWidgets.QLabel()
        controls.addWidget(self.response_standard_label)
        self.response_standard = self.QtWidgets.QComboBox()
        self.response_standard.addItem("BMW", ResponseStandard.BMW.value)
        self.response_standard.addItem("Audi", ResponseStandard.AUDI.value)
        controls.addWidget(self.response_standard)

        self.response_trigger_label = self.QtWidgets.QLabel()
        controls.addWidget(self.response_trigger_label)
        self.response_trigger = self.QtWidgets.QDoubleSpinBox()
        self.response_trigger.setRange(1.0, 99.0)
        self.response_trigger.setDecimals(2)
        self.response_trigger.setValue(10.0)
        self.response_trigger.setSuffix(" %")
        self.response_trigger.setMaximumWidth(105)
        controls.addWidget(self.response_trigger)

        self.response_end_label = self.QtWidgets.QLabel()
        controls.addWidget(self.response_end_label)
        self.response_end_fraction = self.QtWidgets.QDoubleSpinBox()
        self.response_end_fraction.setRange(0.5, 30.0)
        self.response_end_fraction.setDecimals(2)
        self.response_end_fraction.setValue(2.0)
        self.response_end_fraction.setSuffix(" %")
        self.response_end_fraction.setMaximumWidth(105)
        controls.addWidget(self.response_end_fraction)

        self.response_limit_label = self.QtWidgets.QLabel()
        controls.addWidget(self.response_limit_label)
        self.response_t90_limit = self.QtWidgets.QDoubleSpinBox()
        self.response_t90_limit.setRange(0.0, 1000.0)
        self.response_t90_limit.setDecimals(2)
        self.response_t90_limit.setValue(0.0)
        self.response_t90_limit.setSpecialValueText("—")
        self.response_t90_limit.setSuffix(" ms")
        self.response_t90_limit.setMaximumWidth(110)
        controls.addWidget(self.response_t90_limit)

        self.response_analyze_button = self.QtWidgets.QPushButton()
        self.response_analyze_button.clicked.connect(self.analyze_response)
        controls.addWidget(self.response_analyze_button)
        self.response_export_button = self.QtWidgets.QPushButton()
        self.response_export_button.clicked.connect(self.export_response)
        controls.addWidget(self.response_export_button)
        root.addLayout(controls)

        event_row = self.QtWidgets.QHBoxLayout()
        self.response_event_label = self.QtWidgets.QLabel()
        event_row.addWidget(self.response_event_label)
        self.response_event_combo = self.QtWidgets.QComboBox()
        self.response_event_combo.setMinimumWidth(180)
        self.response_event_combo.currentIndexChanged.connect(self.refresh_response_plot)
        event_row.addWidget(self.response_event_combo)
        self.response_status = self.QtWidgets.QLabel()
        self.response_status.setTextInteractionFlags(self.QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        event_row.addWidget(self.response_status, 1)
        root.addLayout(event_row)

        splitter = self.QtWidgets.QSplitter(self.QtCore.Qt.Orientation.Vertical)
        self.response_plot_area = self.pg.GraphicsLayoutWidget()
        splitter.addWidget(self.response_plot_area)
        self.response_table = self._new_table()
        splitter.addWidget(self.response_table)
        splitter.setSizes([560, 260])
        root.addWidget(splitter, 1)

        self.window.tabs.addTab(self.response_page, "")

    def _build_hysteresis_page(self):
        self.hysteresis_page = self.QtWidgets.QWidget()
        root = self.QtWidgets.QVBoxLayout(self.hysteresis_page)

        controls = self.QtWidgets.QHBoxLayout()
        self.hysteresis_open_button = self.QtWidgets.QPushButton()
        self.hysteresis_open_button.clicked.connect(self.open_hysteresis_file)
        controls.addWidget(self.hysteresis_open_button)
        self.hysteresis_file_label = self.QtWidgets.QLabel()
        self.hysteresis_file_label.setMinimumWidth(220)
        self.hysteresis_file_label.setTextInteractionFlags(self.QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        controls.addWidget(self.hysteresis_file_label, 1)

        self.hysteresis_standard_label = self.QtWidgets.QLabel()
        controls.addWidget(self.hysteresis_standard_label)
        self.hysteresis_standard = self.QtWidgets.QComboBox()
        self.hysteresis_standard.addItem("BMW", HysteresisStandard.BMW.value)
        self.hysteresis_standard.addItem("Audi", HysteresisStandard.AUDI.value)
        self.hysteresis_standard.currentIndexChanged.connect(self._sync_hysteresis_controls)
        controls.addWidget(self.hysteresis_standard)

        self.hysteresis_limit_label = self.QtWidgets.QLabel()
        controls.addWidget(self.hysteresis_limit_label)
        self.hysteresis_limit = self.QtWidgets.QDoubleSpinBox()
        self.hysteresis_limit.setRange(0.0, 100.0)
        self.hysteresis_limit.setDecimals(2)
        self.hysteresis_limit.setValue(0.0)
        self.hysteresis_limit.setSpecialValueText("—")
        self.hysteresis_limit.setSuffix(" %")
        self.hysteresis_limit.setMaximumWidth(100)
        controls.addWidget(self.hysteresis_limit)

        self.hysteresis_analyze_button = self.QtWidgets.QPushButton()
        self.hysteresis_analyze_button.clicked.connect(self.analyze_hysteresis)
        controls.addWidget(self.hysteresis_analyze_button)
        self.hysteresis_export_button = self.QtWidgets.QPushButton()
        self.hysteresis_export_button.clicked.connect(self.export_hysteresis)
        controls.addWidget(self.hysteresis_export_button)
        root.addLayout(controls)

        audi_row = self.QtWidgets.QHBoxLayout()
        self.audi_mapping_label = self.QtWidgets.QLabel()
        audi_row.addWidget(self.audi_mapping_label)
        self.audi_soft = self.QtWidgets.QLineEdit()
        self.audi_kfm = self.QtWidgets.QLineEdit()
        self.audi_hard = self.QtWidgets.QLineEdit()
        for edit in (self.audi_soft, self.audi_kfm, self.audi_hard):
            edit.setMaximumWidth(95)
        self.audi_soft_label = self.QtWidgets.QLabel()
        self.audi_kfm_label = self.QtWidgets.QLabel()
        self.audi_hard_label = self.QtWidgets.QLabel()
        for label, edit in (
            (self.audi_soft_label, self.audi_soft),
            (self.audi_kfm_label, self.audi_kfm),
            (self.audi_hard_label, self.audi_hard),
        ):
            audi_row.addWidget(label)
            audi_row.addWidget(edit)
        self.hysteresis_status = self.QtWidgets.QLabel()
        self.hysteresis_status.setTextInteractionFlags(self.QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        audi_row.addWidget(self.hysteresis_status, 1)
        root.addLayout(audi_row)

        splitter = self.QtWidgets.QSplitter(self.QtCore.Qt.Orientation.Vertical)
        self.hysteresis_plot_area = self.pg.GraphicsLayoutWidget()
        splitter.addWidget(self.hysteresis_plot_area)
        self.hysteresis_tables = self.QtWidgets.QTabWidget()
        self.hysteresis_summary_table = self._new_table()
        self.hysteresis_run_table = self._new_table()
        self.hysteresis_tables.addTab(self.hysteresis_summary_table, "")
        self.hysteresis_tables.addTab(self.hysteresis_run_table, "")
        splitter.addWidget(self.hysteresis_tables)
        splitter.setSizes([530, 290])
        root.addWidget(splitter, 1)

        self.window.tabs.addTab(self.hysteresis_page, "")
        self._sync_hysteresis_controls()

    def _file_filter(self) -> str:
        return self._text(
            "试验数据 (*.dat *.csv *.xlsx *.xlsm);;所有文件 (*)",
            "Test data (*.dat *.csv *.xlsx *.xlsm);;All files (*)",
        )

    def open_response_file(self):
        path, _ = self.QtWidgets.QFileDialog.getOpenFileName(
            self.window,
            self._text("打开响应时间数据", "Open response-time data"),
            "",
            self._file_filter(),
        )
        if not path:
            return
        try:
            self.response_dataset = load_dynamic_test_data(path)
            self.response_path = Path(path)
            self.response_file_label.setText(str(self.response_path))
            mapping = self.response_dataset.metadata.get("inferred_mapping")
            if mapping:
                self.response_status.setText(
                    self._text(
                        f"已自动识别无表头通道：T={mapping['time_column_1based']} / F={mapping['load_column_1based']} / I={mapping['current_column_1based']} / X={mapping['displacement_column_1based']}",
                        f"Headerless channels inferred: T={mapping['time_column_1based']} / F={mapping['load_column_1based']} / I={mapping['current_column_1based']} / X={mapping['displacement_column_1based']}",
                    )
                )
            else:
                self.response_status.setText(self._text("数据已加载", "Data loaded"))
        except Exception as exc:
            self.QtWidgets.QMessageBox.critical(self.window, self._text("导入错误", "Import error"), str(exc))

    def analyze_response(self):
        if self.response_dataset is None:
            self.QtWidgets.QMessageBox.information(
                self.window,
                self._text("响应时间", "Response Time"),
                self._text("请先打开响应时间原始数据。", "Open response-time raw data first."),
            )
            return
        try:
            standard = ResponseStandard(self.response_standard.currentData())
            limit = self.response_t90_limit.value() or None
            config = ResponseConfig(
                standard=standard,
                trigger_fraction=self.response_trigger.value() / 100.0,
                end_average_fraction=self.response_end_fraction.value() / 100.0,
                t90_limit_ms=limit,
            )
            self.response_result = analyze_response_time(self.response_dataset, config)
            self._fill_table(self.response_table, self.response_result.events)
            self.response_event_combo.blockSignals(True)
            self.response_event_combo.clear()
            for _, row in self.response_result.events.iterrows():
                text = self._text(
                    f"事件 {int(row['Event ID'])} — {row['Direction']} / {row['Force Change']}",
                    f"Event {int(row['Event ID'])} — {row['Direction']} / {row['Force Change']}",
                )
                self.response_event_combo.addItem(text, int(row["Event ID"]))
            self.response_event_combo.blockSignals(False)
            self.refresh_response_plot()
            sample_rate = float(self.response_result.events["Sample Rate Hz"].iloc[0])
            self.response_status.setText(
                self._text(
                    f"分析完成：{len(self.response_result.events)} 个电流跳变事件；采样率约 {sample_rate:.2f} Hz",
                    f"Analysis complete: {len(self.response_result.events)} current-step event(s); sample rate ≈ {sample_rate:.2f} Hz",
                )
            )
        except Exception as exc:
            self.QtWidgets.QMessageBox.critical(self.window, self._text("分析错误", "Analysis error"), str(exc))

    def _axis_style(self, plot, left: str, units: str | None = None):
        plot.showGrid(x=True, y=True, alpha=0.25)
        plot.setLabel("left", left, units=units)
        plot.setLabel("bottom", self._text("时间", "Time"), units="s")
        plot.setClipToView(True)
        plot.setDownsampling(auto=True, mode="peak")
        background = getattr(self.window, "_plot_background_color", "#ffffff")
        foreground = getattr(self.window, "_plot_foreground_color", "#202020")
        plot.getAxis("left").setTextPen(foreground)
        plot.getAxis("bottom").setTextPen(foreground)
        self.response_plot_area.setBackground(background)
        self.hysteresis_plot_area.setBackground(background)

    def refresh_response_plot(self):
        self.response_plot_area.clear()
        if self.response_result is None or self.response_result.events.empty:
            return
        event_id = self.response_event_combo.currentData()
        if event_id is None:
            event_id = int(self.response_result.events["Event ID"].iloc[0])
        row = self.response_result.events[self.response_result.events["Event ID"] == event_id].iloc[0]
        data = self.response_result.processed[
            self.response_result.processed[TIME].between(row["Segment Start s"], row["Segment End s"])
        ]
        t = data[TIME].to_numpy(float)

        current_plot = self.response_plot_area.addPlot(row=0, col=0)
        self._axis_style(current_plot, self._text("阀电流", "Valve current"), "A")
        current_plot.plot(t, data[CURRENT].to_numpy(float), pen=self.pg.mkPen(width=1.2))
        current_plot.addLine(x=float(row["t0 s"]), pen=self.pg.mkPen(style=self.QtCore.Qt.PenStyle.DashLine))
        for value in (row["Current Start A"], row["Trigger Current A"], row["Current End A"]):
            current_plot.addLine(y=float(value), pen=self.pg.mkPen(style=self.QtCore.Qt.PenStyle.DotLine))

        force_plot = self.response_plot_area.addPlot(row=1, col=0)
        force_plot.setXLink(current_plot)
        self._axis_style(force_plot, self._text("阻尼力", "Damping force"), "N")
        force_plot.plot(t, data[LOAD].to_numpy(float), pen=self.pg.mkPen(width=1.4))
        force_plot.addLine(x=float(row["t0 s"]), pen=self.pg.mkPen(style=self.QtCore.Qt.PenStyle.DashLine))
        for value in (row["F0 N"], row["F63 N"], row["F90 N"], row["F100 N"]):
            force_plot.addLine(y=float(value), pen=self.pg.mkPen(style=self.QtCore.Qt.PenStyle.DotLine))
        for key in ("Switch Time t63 ms", "Switch Time t90 ms"):
            elapsed = float(row[key])
            if np.isfinite(elapsed):
                force_plot.addLine(
                    x=float(row["t0 s"]) + elapsed / 1000.0,
                    pen=self.pg.mkPen(style=self.QtCore.Qt.PenStyle.DashLine),
                )

        velocity_plot = self.response_plot_area.addPlot(row=2, col=0)
        velocity_plot.setXLink(current_plot)
        self._axis_style(velocity_plot, self._text("速度", "Velocity"), "m/s")
        velocity_plot.plot(t, data[VELOCITY].to_numpy(float), pen=self.pg.mkPen(width=1.2))
        velocity_plot.addLine(x=float(row["t0 s"]), pen=self.pg.mkPen(style=self.QtCore.Qt.PenStyle.DashLine))

    def export_response(self):
        if self.response_result is None:
            return
        default = (self.response_path.stem + "_response.xlsx") if self.response_path else "response.xlsx"
        path, _ = self.QtWidgets.QFileDialog.getSaveFileName(
            self.window,
            self._text("导出响应时间结果", "Export response-time result"),
            default,
            "Excel (*.xlsx)",
        )
        if path:
            try:
                export_response_xlsx(self.response_result, path)
            except Exception as exc:
                self.QtWidgets.QMessageBox.critical(self.window, self._text("导出错误", "Export error"), str(exc))

    def open_hysteresis_file(self):
        path, _ = self.QtWidgets.QFileDialog.getOpenFileName(
            self.window,
            self._text("打开迟滞试验数据", "Open hysteresis data"),
            "",
            self._file_filter(),
        )
        if not path:
            return
        try:
            self.hysteresis_dataset = load_dynamic_test_data(path)
            self.hysteresis_path = Path(path)
            self.hysteresis_file_label.setText(str(self.hysteresis_path))
            self.hysteresis_status.setText(self._text("数据已加载", "Data loaded"))
        except Exception as exc:
            self.QtWidgets.QMessageBox.critical(self.window, self._text("导入错误", "Import error"), str(exc))

    @staticmethod
    def _optional_float(edit) -> float | None:
        text = edit.text().strip()
        if not text:
            return None
        return float(text)

    def analyze_hysteresis(self):
        if self.hysteresis_dataset is None:
            self.QtWidgets.QMessageBox.information(
                self.window,
                self._text("迟滞", "Hysteresis"),
                self._text("请先打开迟滞试验原始数据。", "Open hysteresis raw data first."),
            )
            return
        try:
            standard = HysteresisStandard(self.hysteresis_standard.currentData())
            limit = self.hysteresis_limit.value() or None
            config = HysteresisConfig(
                standard=standard,
                limit_percent=limit,
                audi_soft_current_a=self._optional_float(self.audi_soft),
                audi_kfm_current_a=self._optional_float(self.audi_kfm),
                audi_hard_current_a=self._optional_float(self.audi_hard),
            )
            self.hysteresis_result = analyze_hysteresis(self.hysteresis_dataset, config)
            self._fill_table(self.hysteresis_summary_table, self.hysteresis_result.summary)
            self._fill_table(self.hysteresis_run_table, self.hysteresis_result.runs)
            self.refresh_hysteresis_plot()
            self.hysteresis_status.setText(
                self._text(
                    f"分析完成：{len(self.hysteresis_result.summary)} 条迟滞结果；未设置客户限值时不判定合格/不合格",
                    f"Analysis complete: {len(self.hysteresis_result.summary)} hysteresis result(s); no pass/fail without a customer limit",
                )
            )
        except Exception as exc:
            self.QtWidgets.QMessageBox.critical(self.window, self._text("分析错误", "Analysis error"), str(exc))

    def refresh_hysteresis_plot(self):
        self.hysteresis_plot_area.clear()
        if self.hysteresis_result is None:
            return
        standard = self.hysteresis_result.settings.get("OEM Profile")
        background = getattr(self.window, "_plot_background_color", "#ffffff")
        self.hysteresis_plot_area.setBackground(background)
        if standard == "bmw":
            runs = self.hysteresis_result.runs
            previous = None
            for row_index, motion in enumerate(("Rebound", "Compression")):
                plot = self.hysteresis_plot_area.addPlot(row=row_index, col=0)
                plot.showGrid(x=True, y=True, alpha=0.25)
                plot.setLabel("left", self._text("复原载荷" if motion == "Rebound" else "压缩载荷", motion), units="N")
                plot.setLabel("bottom", self._text("电流", "Current"), units="A")
                if previous is not None:
                    plot.setXLink(previous)
                previous = plot
                subset = runs[runs["Direction"] == motion]
                for index, sweep in enumerate(("Up", "Down")):
                    curve = subset[subset["Sweep Direction"] == sweep].sort_values("Current Label A")
                    if curve.empty:
                        continue
                    plot.plot(
                        curve["Current Label A"].to_numpy(float),
                        curve["Force N"].to_numpy(float),
                        pen=self.pg.intColor(index, hues=2),
                        symbol="o",
                    )
        else:
            runs = self.hysteresis_result.runs
            plot = self.hysteresis_plot_area.addPlot(row=0, col=0)
            plot.showGrid(x=True, y=True, alpha=0.25)
            plot.setLabel("left", self._text("行程中心载荷", "Center-stroke force"), units="N")
            plot.setLabel("bottom", self._text("电流平台顺序", "Current plateau order"))
            for index, motion in enumerate(("Rebound", "Compression")):
                curve = runs[runs["Direction"] == motion].sort_values("Block Order")
                if curve.empty:
                    continue
                plot.plot(
                    curve["Block Order"].to_numpy(float),
                    curve["Mean Force N"].to_numpy(float),
                    pen=self.pg.intColor(index, hues=2),
                    symbol="o",
                )

    def export_hysteresis(self):
        if self.hysteresis_result is None:
            return
        default = (self.hysteresis_path.stem + "_hysteresis.xlsx") if self.hysteresis_path else "hysteresis.xlsx"
        path, _ = self.QtWidgets.QFileDialog.getSaveFileName(
            self.window,
            self._text("导出迟滞结果", "Export hysteresis result"),
            default,
            "Excel (*.xlsx)",
        )
        if path:
            try:
                export_hysteresis_xlsx(self.hysteresis_result, path)
            except Exception as exc:
                self.QtWidgets.QMessageBox.critical(self.window, self._text("导出错误", "Export error"), str(exc))

    def _fill_table(self, table, frame: pd.DataFrame):
        table.clear()
        table.setRowCount(len(frame))
        table.setColumnCount(len(frame.columns))
        table.setHorizontalHeaderLabels([str(column) for column in frame.columns])
        for row_index in range(len(frame)):
            for col_index, column in enumerate(frame.columns):
                value = frame.iloc[row_index, col_index]
                item = self.QtWidgets.QTableWidgetItem(format_value(str(column), value))
                item.setTextAlignment(int(self.QtCore.Qt.AlignmentFlag.AlignCenter))
                table.setItem(row_index, col_index, item)
        table.resizeColumnsToContents()

    def _sync_hysteresis_controls(self):
        audi = self.hysteresis_standard.currentData() == HysteresisStandard.AUDI.value
        for widget in (
            self.audi_mapping_label,
            self.audi_soft_label,
            self.audi_soft,
            self.audi_kfm_label,
            self.audi_kfm,
            self.audi_hard_label,
            self.audi_hard,
        ):
            widget.setVisible(audi)

    def apply_language(self, language: str):
        self.response_open_button.setText(self._text("打开响应数据", "Open Response Data"))
        self.response_standard_label.setText(self._text("规范", "Standard"))
        self.response_trigger_label.setText(self._text("电流触发", "Current trigger"))
        self.response_end_label.setText(self._text("终值平均", "End average"))
        self.response_limit_label.setText(self._text("t90限值", "t90 limit"))
        self.response_analyze_button.setText(self._text("分析响应", "Analyze Response"))
        self.response_export_button.setText(self._text("导出 Excel", "Export Excel"))
        self.response_event_label.setText(self._text("显示事件", "Display event"))
        if self.response_path is None:
            self.response_file_label.setText(self._text("未加载响应数据", "No response data loaded"))

        self.hysteresis_open_button.setText(self._text("打开迟滞数据", "Open Hysteresis Data"))
        self.hysteresis_standard_label.setText(self._text("规范", "Standard"))
        self.hysteresis_limit_label.setText(self._text("迟滞限值", "Hysteresis limit"))
        self.hysteresis_analyze_button.setText(self._text("分析迟滞", "Analyze Hysteresis"))
        self.hysteresis_export_button.setText(self._text("导出 Excel", "Export Excel"))
        self.audi_mapping_label.setText(self._text("Audi电流状态", "Audi current states"))
        self.audi_soft_label.setText(self._text("软", "Soft"))
        self.audi_kfm_label.setText("KFM")
        self.audi_hard_label.setText(self._text("硬", "Hard"))
        placeholder = self._text("自动", "Auto")
        for edit in (self.audi_soft, self.audi_kfm, self.audi_hard):
            edit.setPlaceholderText(placeholder)
        if self.hysteresis_path is None:
            self.hysteresis_file_label.setText(self._text("未加载迟滞数据", "No hysteresis data loaded"))

        self.window.tabs.setTabText(
            self.window.tabs.indexOf(self.response_page),
            self._text("响应时间", "Response Time"),
        )
        self.window.tabs.setTabText(
            self.window.tabs.indexOf(self.hysteresis_page),
            self._text("迟滞", "Hysteresis"),
        )
        self.hysteresis_tables.setTabText(
            self.hysteresis_tables.indexOf(self.hysteresis_summary_table),
            self._text("迟滞汇总", "Hysteresis Summary"),
        )
        self.hysteresis_tables.setTabText(
            self.hysteresis_tables.indexOf(self.hysteresis_run_table),
            self._text("工况明细", "Run Detail"),
        )
        self._sync_hysteresis_controls()
