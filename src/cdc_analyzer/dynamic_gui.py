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
    load_dynamic_test_data,
)
from .dynamic_export import export_hysteresis_xlsx, export_response_xlsx
from .formatting import format_value
from .response_multistage import analyze_response_time_multistage


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


ZH_HEADERS = {
    "Event ID": "事件编号",
    "Block ID": "数据块",
    "OEM": "客户规范",
    "Stage": "切换阶段",
    "Current Start A": "起始电流 / A",
    "Current End A": "终止电流 / A",
    "Current Delta A": "电流变化量 / A",
    "Trigger Fraction": "电流触发比例",
    "Trigger Current A": "10%触发电流 / A",
    "t0 s": "t0 / s",
    "Displacement at t0 mm": "t0位移 / mm",
    "Velocity at t0 m/s": "t0实测速度 / m/s",
    "Target Velocity m/s": "目标速度 / m/s",
    "Direction": "方向",
    "Force Change": "阻尼力变化",
    "F0 N": "F0 / N",
    "F1 N": "F1% / N",
    "F10 N": "F10% / N",
    "F63 N": "F63% / N",
    "F90 N": "F90% / N",
    "F100 N": "F100% / N",
    "Delta F N": "阻尼力变化量 / N",
    "Dead Time t1 ms": "t1% / ms",
    "Switch Time t10 ms": "t10% / ms",
    "Switch Time t63 ms": "t63% / ms",
    "Switch Time t90 ms": "t90% / ms",
    "Gradient 63 N/s": "63%力梯度 / (N/s)",
    "Gradient 90 N/s": "90%力梯度 / (N/s)",
    "Sample Rate Hz": "采样率 / Hz",
    "Status": "状态",
    "Issues": "数据提示",
    "Current A": "电流 / A",
    "Up Force N": "升电流阻尼力 / N",
    "Down Force N": "降电流阻尼力 / N",
    "Reference Damping Force N": "参考阻尼力 / N",
    "Hysteresis N": "迟滞 / N",
    "Hysteresis %": "迟滞 / %",
    "Limit %": "限值 / %",
    "Block Order": "数据块顺序",
    "Current Label A": "电流档位 / A",
    "Actual Current A": "实测电流 / A",
    "Sweep Direction": "电流扫描方向",
    "Force N": "阻尼力 / N",
    "Abs Force N": "阻尼力幅值 / N",
    "Speed m/s": "速度 / m/s",
    "Crossing Count": "交点数",
    "State": "电流状态",
    "First Cycle Force N": "第1循环阻尼力 / N",
    "Mean Force N": "平均阻尼力 / N",
    "Raw Cycle Count": "原始循环数",
    "Retained Cycle Count": "有效循环数",
    "Mean Speed m/s": "平均速度 / m/s",
    "Excursion State": "往返状态",
    "KFM Before N": "KFM前阻尼力 / N",
    "KFM After N": "KFM后阻尼力 / N",
    "Spread Fmax-Fmin N": "Fmax-Fmin / N",
    "First Cycle Delta N": "第1循环差值 / N",
}

RESPONSE_TABLE_COLUMNS = [
    "Event ID",
    "Stage",
    "Direction",
    "Current Start A",
    "Current End A",
    "Target Velocity m/s",
    "F0 N",
    "F1 N",
    "F10 N",
    "F63 N",
    "F90 N",
    "F100 N",
    "Dead Time t1 ms",
    "Switch Time t10 ms",
    "Switch Time t63 ms",
    "Switch Time t90 ms",
    "Sample Rate Hz",
    "Status",
    "Issues",
]


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
        self.response_export_image_button = self.QtWidgets.QPushButton()
        self.response_export_image_button.clicked.connect(self.export_response_image)
        controls.addWidget(self.response_export_image_button)
        root.addLayout(controls)

        event_row = self.QtWidgets.QHBoxLayout()
        self.response_event_label = self.QtWidgets.QLabel()
        event_row.addWidget(self.response_event_label)
        self.response_event_combo = self.QtWidgets.QComboBox()
        self.response_event_combo.setMinimumWidth(320)
        self.response_event_combo.currentIndexChanged.connect(self.refresh_response_plot)
        event_row.addWidget(self.response_event_combo)
        self.response_status = self.QtWidgets.QLabel()
        self.response_status.setTextInteractionFlags(self.QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        event_row.addWidget(self.response_status, 1)
        root.addLayout(event_row)

        splitter = self.QtWidgets.QSplitter(self.QtCore.Qt.Orientation.Vertical)
        self.response_plot_area = self.pg.GraphicsLayoutWidget()
        self.response_plot_area.setMinimumHeight(650)
        splitter.addWidget(self.response_plot_area)
        self.response_table = self._new_table()
        self.response_table.cellClicked.connect(self._response_table_clicked)
        splitter.addWidget(self.response_table)
        splitter.setSizes([740, 180])
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
        self.hysteresis_export_image_button = self.QtWidgets.QPushButton()
        self.hysteresis_export_image_button.clicked.connect(self.export_hysteresis_image)
        controls.addWidget(self.hysteresis_export_image_button)
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
        self.hysteresis_plot_area.setMinimumHeight(540)
        splitter.addWidget(self.hysteresis_plot_area)
        self.hysteresis_tables = self.QtWidgets.QTabWidget()
        self.hysteresis_summary_table = self._new_table()
        self.hysteresis_run_table = self._new_table()
        self.hysteresis_tables.addTab(self.hysteresis_summary_table, "")
        self.hysteresis_tables.addTab(self.hysteresis_run_table, "")
        splitter.addWidget(self.hysteresis_tables)
        splitter.setSizes([620, 200])
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
            self.response_result = analyze_response_time_multistage(self.response_dataset, config)
            self._fill_table(self.response_table, self._response_display_frame())
            self._rebuild_response_event_combo()
            self.refresh_response_plot()
            sample_rate = float(self.response_result.events["Sample Rate Hz"].iloc[0])
            self.response_status.setText(
                self._text(
                    f"整文件分析完成：识别 {len(self.response_result.events)} 个响应阶段；采样率约 {sample_rate:.2f} Hz",
                    f"Full-file analysis complete: {len(self.response_result.events)} response event(s); sample rate ≈ {sample_rate:.2f} Hz",
                )
            )
        except Exception as exc:
            self.QtWidgets.QMessageBox.critical(self.window, self._text("分析错误", "Analysis error"), str(exc))

    def _response_display_frame(self) -> pd.DataFrame:
        if self.response_result is None:
            return pd.DataFrame()
        columns = [column for column in RESPONSE_TABLE_COLUMNS if column in self.response_result.events.columns]
        return self.response_result.events[columns]

    def _rebuild_response_event_combo(self):
        if self.response_result is None:
            return
        self.response_event_combo.blockSignals(True)
        self.response_event_combo.clear()
        for _, row in self.response_result.events.iterrows():
            direction = self._display_value("Direction", row["Direction"])
            text = self._text(
                f"{int(row['Event ID'])}｜{self._display_value('Stage', row['Stage'])}｜{direction}｜{float(row['Current Start A']):.2f}→{float(row['Current End A']):.2f} A",
                f"{int(row['Event ID'])} | {row['Stage']} | {row['Direction']} | {float(row['Current Start A']):.2f}→{float(row['Current End A']):.2f} A",
            )
            self.response_event_combo.addItem(text, int(row["Event ID"]))
        self.response_event_combo.blockSignals(False)
        if self.response_event_combo.count():
            self.response_event_combo.setCurrentIndex(0)

    def _response_table_clicked(self, row_index: int, _column_index: int):
        if self.response_result is None or row_index >= len(self.response_result.events):
            return
        event_id = int(self.response_result.events.iloc[row_index]["Event ID"])
        combo_index = self.response_event_combo.findData(event_id)
        if combo_index >= 0:
            self.response_event_combo.setCurrentIndex(combo_index)

    def _axis_style(self, plot, left: str, units: str | None = None):
        from PySide6 import QtGui

        plot.showGrid(x=True, y=True, alpha=0.22)
        plot.setLabel("left", left, units=units, **{"font-size": "11pt"})
        plot.setLabel("bottom", self._text("时间", "Time"), units="s", **{"font-size": "11pt"})
        plot.setClipToView(True)
        plot.setDownsampling(auto=True, mode="peak")
        plot.setMinimumHeight(205)
        background = getattr(self.window, "_plot_background_color", "#ffffff")
        foreground = getattr(self.window, "_plot_foreground_color", "#202020")
        tick_font = QtGui.QFont()
        tick_font.setPointSize(10)
        for axis_name in ("left", "bottom"):
            axis = plot.getAxis(axis_name)
            axis.setTextPen(foreground)
            axis.setPen(foreground)
            if hasattr(axis, "setTickFont"):
                axis.setTickFont(tick_font)
        self.response_plot_area.setBackground(background)
        self.hysteresis_plot_area.setBackground(background)

    def _marker_pen(self, width: float = 1.2):
        foreground = getattr(self.window, "_plot_foreground_color", "#202020")
        return self.pg.mkPen(foreground, width=width, style=self.QtCore.Qt.PenStyle.DashLine)

    def _curve_pen(self, width: float = 2.5):
        foreground = getattr(self.window, "_plot_foreground_color", "#202020")
        return self.pg.mkPen(foreground, width=width)

    def _text_item(self, text: str, x: float, y: float, anchor=(0, 1)):
        foreground = getattr(self.window, "_plot_foreground_color", "#202020")
        item = self.pg.TextItem(anchor=anchor)
        item.setHtml(
            f"<div style='font-size:11pt;font-weight:600;color:{foreground};background-color:rgba(255,255,255,0);'>{text}</div>"
        )
        item.setPos(float(x), float(y))
        return item

    def _add_horizontal_marker(self, plot, value: float, label: str, x: float):
        if not np.isfinite(value):
            return
        plot.addLine(y=float(value), pen=self._marker_pen())
        plot.addItem(self._text_item(label, x, float(value), anchor=(0, 1)))

    def _add_vertical_marker(self, plot, value: float, label: str | None = None, y: float | None = None):
        if not np.isfinite(value):
            return
        plot.addLine(x=float(value), pen=self._marker_pen())
        if label is not None and y is not None and np.isfinite(y):
            plot.addItem(self._text_item(label, float(value), float(y), anchor=(0, 0)))

    def _add_intersection(self, plot, x: float, y: float, label: str):
        if not np.isfinite(x) or not np.isfinite(y):
            return
        foreground = getattr(self.window, "_plot_foreground_color", "#202020")
        plot.plot(
            [float(x)],
            [float(y)],
            pen=None,
            symbol="o",
            symbolSize=9,
            symbolPen=self.pg.mkPen(foreground, width=1.5),
            symbolBrush=self.pg.mkBrush(foreground),
        )
        plot.addItem(self._text_item(label, float(x), float(y), anchor=(0, 1)))

    def _add_audi_fig15_windows(self, force_plot, row):
        if str(row.get("OEM", "")).upper() != "AUDI":
            return
        foreground = getattr(self.window, "_plot_foreground_color", "#202020")
        brush = self.pg.mkBrush(100, 160, 220, 35)
        pen = self.pg.mkPen(foreground, width=1.0, style=self.QtCore.Qt.PenStyle.DashLine)
        for start_key, end_key, label in (
            ("Force Start Window Start s", "Force Start Window End s", self._text("起始参考区", "Start reference")),
            ("Force End Window Start s", "Force End Window End s", self._text("F100终值平均区", "F100 end-average")),
        ):
            start = float(row.get(start_key, np.nan))
            end = float(row.get(end_key, np.nan))
            if not np.isfinite(start) or not np.isfinite(end) or end <= start:
                continue
            region = self.pg.LinearRegionItem(values=(start, end), movable=False, brush=brush, pen=pen)
            region.setZValue(-10)
            force_plot.addItem(region)
            view = force_plot.viewRange()[1]
            y = view[1] if len(view) == 2 else float(row["F0 N"])
            force_plot.addItem(self._text_item(label, (start + end) / 2.0, y, anchor=(0.5, 0)))

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
        ].copy()
        if "Block ID" in data.columns and "Block ID" in row:
            data = data[data["Block ID"] == int(row["Block ID"])]
        if data.empty:
            return
        t = data[TIME].to_numpy(float)
        x_label = float(t[0] + 0.02 * max(float(t[-1] - t[0]), 1e-9))
        title_direction = self._display_value("Direction", row["Direction"])
        title_stage = self._display_value("Stage", row["Stage"])

        current_plot = self.response_plot_area.addPlot(row=0, col=0)
        current_plot.setTitle(
            self._text(f"电流响应｜{title_stage}｜{title_direction}", f"Current Response | {row['Stage']} | {row['Direction']}"),
            size="12pt",
        )
        self._axis_style(current_plot, self._text("阀电流", "Valve current"), "A")
        current_plot.plot(t, data[CURRENT].to_numpy(float), pen=self._curve_pen(2.5))
        self._add_horizontal_marker(current_plot, float(row["Trigger Current A"]), "I10% / 10%", x_label)
        self._add_horizontal_marker(current_plot, float(row["Current End A"]), "I100% / 100%", x_label)
        current_y = float(row["Trigger Current A"])
        self._add_vertical_marker(current_plot, float(row["t0 s"]), "t0", current_y)
        self._add_intersection(current_plot, float(row["t0 s"]), current_y, "I10%")

        force_plot = self.response_plot_area.addPlot(row=1, col=0)
        force_plot.setXLink(current_plot)
        force_plot.setTitle(self._text("阻尼力响应", "Damping Force Response"), size="12pt")
        self._axis_style(force_plot, self._text("阻尼力", "Damping force"), "N")
        force_plot.plot(t, data[LOAD].to_numpy(float), pen=self._curve_pen(2.8))
        force_values = data[LOAD].to_numpy(float)
        direction_text = self._text("复原 (+)" if row["Direction"] == "Rebound" else "压缩 (-)", "Rebound (+)" if row["Direction"] == "Rebound" else "Compression (-)")
        force_plot.addItem(self._text_item(direction_text, x_label, float(np.nanmax(force_values) if row["Direction"] == "Rebound" else np.nanmin(force_values)), anchor=(0, 1)))

        self._add_horizontal_marker(force_plot, float(row["F0 N"]), "F0", x_label)
        threshold_specs = (
            ("F1 N", "t1 s", "F1%", "t1%"),
            ("F10 N", "t10 s", "F10%", "t10%"),
            ("F63 N", "t63 s", "F63%", "t63%"),
            ("F90 N", "t90 s", "F90%", "t90%"),
        )
        y_text = float(np.nanmax(force_values))
        for force_key, time_key, force_label, time_label in threshold_specs:
            force_value = float(row.get(force_key, np.nan))
            time_value = float(row.get(time_key, np.nan))
            self._add_horizontal_marker(force_plot, force_value, force_label, x_label)
            self._add_vertical_marker(force_plot, time_value, time_label, y_text)
            self._add_intersection(force_plot, time_value, force_value, force_label)
        self._add_horizontal_marker(force_plot, float(row["F100 N"]), "F100%", x_label)
        f100_time = 0.5 * (float(row["Force End Window Start s"]) + float(row["Force End Window End s"]))
        self._add_intersection(force_plot, f100_time, float(row["F100 N"]), "F100%")
        self._add_vertical_marker(force_plot, float(row["t0 s"]), "t0", y_text)
        self._add_audi_fig15_windows(force_plot, row)

        velocity_plot = self.response_plot_area.addPlot(row=2, col=0)
        velocity_plot.setXLink(current_plot)
        velocity_plot.setTitle(self._text("速度", "Velocity"), size="12pt")
        self._axis_style(velocity_plot, self._text("速度", "Velocity"), "m/s")
        velocity_plot.plot(t, data[VELOCITY].to_numpy(float), pen=self._curve_pen(2.4))
        target_velocity = float(row.get("Target Velocity m/s", np.nan))
        if np.isfinite(target_velocity):
            self._add_horizontal_marker(
                velocity_plot,
                target_velocity,
                self._text(f"目标速度 {target_velocity:.4f} m/s", f"Target {target_velocity:.4f} m/s"),
                x_label,
            )
        self._add_vertical_marker(velocity_plot, float(row["t0 s"]), "t0", float(row["Velocity at t0 m/s"]))

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

    def export_response_image(self):
        if self.response_result is None:
            return
        event_id = self.response_event_combo.currentData() or 1
        stem = self.response_path.stem if self.response_path else "response"
        path, _ = self.QtWidgets.QFileDialog.getSaveFileName(
            self.window,
            self._text("导出响应时间图片", "Export response-time image"),
            f"{stem}_response_event_{event_id}.png",
            "PNG (*.png)",
        )
        if path:
            if not self.response_plot_area.grab().save(path, "PNG"):
                self.QtWidgets.QMessageBox.warning(self.window, self._text("导出错误", "Export error"), self._text("图片保存失败。", "Failed to save image."))

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
                plot.setMinimumHeight(250)
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
                        pen=self.pg.intColor(index, hues=2, values=1),
                        symbol="o",
                        symbolSize=8,
                    )
        else:
            runs = self.hysteresis_result.runs
            plot = self.hysteresis_plot_area.addPlot(row=0, col=0)
            plot.setMinimumHeight(500)
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
                    pen=self.pg.intColor(index, hues=2, values=1),
                    symbol="o",
                    symbolSize=8,
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

    def export_hysteresis_image(self):
        if self.hysteresis_result is None:
            return
        stem = self.hysteresis_path.stem if self.hysteresis_path else "hysteresis"
        path, _ = self.QtWidgets.QFileDialog.getSaveFileName(
            self.window,
            self._text("导出迟滞图片", "Export hysteresis image"),
            f"{stem}_hysteresis.png",
            "PNG (*.png)",
        )
        if path:
            if not self.hysteresis_plot_area.grab().save(path, "PNG"):
                self.QtWidgets.QMessageBox.warning(self.window, self._text("导出错误", "Export error"), self._text("图片保存失败。", "Failed to save image."))

    def _header(self, column: str) -> str:
        return ZH_HEADERS.get(column, column) if self.window.language == "zh_CN" else column

    def _display_value(self, column: str, value):
        if self.window.language != "zh_CN":
            return str(value)
        text = str(value)
        if column == "Direction":
            return {"Rebound": "复原", "Compression": "压缩"}.get(text, text)
        if column == "Force Change":
            return {"Build-up": "增大", "Decay": "减小"}.get(text, text)
        if column == "Sweep Direction":
            return {"Up": "升电流", "Down": "降电流"}.get(text, text)
        if column in ("Stage", "State", "Excursion State"):
            return text.replace("Soft", "软").replace("Medium", "中间").replace("Hard", "硬")
        if column == "Status":
            return {
                "OK": "正常",
                "Warning": "警告",
                "Invalid": "无效",
                "Not evaluated": "未判定",
                "Insufficient cycles": "循环不足",
                "PASS": "合格",
                "FAIL": "不合格",
            }.get(text, text)
        return text

    def _fill_table(self, table, frame: pd.DataFrame):
        table.clear()
        table.setRowCount(len(frame))
        table.setColumnCount(len(frame.columns))
        table.setHorizontalHeaderLabels([self._header(str(column)) for column in frame.columns])
        for row_index in range(len(frame)):
            for col_index, column in enumerate(frame.columns):
                value = frame.iloc[row_index, col_index]
                if isinstance(value, str):
                    rendered = self._display_value(str(column), value)
                else:
                    rendered = format_value(str(column), value)
                item = self.QtWidgets.QTableWidgetItem(rendered)
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
        self.response_analyze_button.setText(self._text("分析整文件", "Analyze Full File"))
        self.response_export_button.setText(self._text("导出 Excel", "Export Excel"))
        self.response_export_image_button.setText(self._text("导出图片", "Export Image"))
        self.response_event_label.setText(self._text("响应阶段", "Response event"))
        if self.response_path is None:
            self.response_file_label.setText(self._text("未加载响应数据", "No response data loaded"))

        self.hysteresis_open_button.setText(self._text("打开迟滞数据", "Open Hysteresis Data"))
        self.hysteresis_standard_label.setText(self._text("规范", "Standard"))
        self.hysteresis_limit_label.setText(self._text("迟滞限值", "Hysteresis limit"))
        self.hysteresis_analyze_button.setText(self._text("分析迟滞", "Analyze Hysteresis"))
        self.hysteresis_export_button.setText(self._text("导出 Excel", "Export Excel"))
        self.hysteresis_export_image_button.setText(self._text("导出图片", "Export Image"))
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
        if self.response_result is not None:
            self._fill_table(self.response_table, self._response_display_frame())
            self._rebuild_response_event_combo()
            self.refresh_response_plot()
        if self.hysteresis_result is not None:
            self._fill_table(self.hysteresis_summary_table, self.hysteresis_result.summary)
            self._fill_table(self.hysteresis_run_table, self.hysteresis_result.runs)
            self.refresh_hysteresis_plot()
        self._sync_hysteresis_controls()
