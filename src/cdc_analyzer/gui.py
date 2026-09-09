from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from .analysis import AnalyzerConfig, CDCAnalyzer, EvaluationProfile
from .export import export_xlsx
from .formatting import format_value
from .i18n import DEFAULT_LANGUAGE, display_channel, display_column, display_value, tr
from .image_export import export_plot_widget_png
from .parser import DataSet, load_test_data
from .plotting import PlotSelection, available_plot_channels, evaluation_overlay, filter_processed_data, same_units, unit_for_channel


def _qt_imports():
    try:
        from PySide6 import QtCore, QtWidgets
        import pyqtgraph as pg
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("GUI dependencies are not installed. Run: python -m pip install -e .[gui]") from exc
    return QtCore, QtWidgets, pg


def _build_gui_classes():
    QtCore, QtWidgets, pg = _qt_imports()
    from PySide6 import QtGui

    class CurveColorItemDelegate(QtWidgets.QStyledItemDelegate):
        """Preserve each curve color while a Y-field row is selected."""

        def paint(self, painter, option, index):
            styled = QtWidgets.QStyleOptionViewItem(option)
            self.initStyleOption(styled, index)
            if styled.state & QtWidgets.QStyle.StateFlag.State_Selected:
                brush = index.data(QtCore.Qt.ItemDataRole.ForegroundRole)
                if brush is not None:
                    styled.palette.setBrush(
                        QtGui.QPalette.ColorRole.HighlightedText, brush
                    )
            style = styled.widget.style() if styled.widget else QtWidgets.QApplication.style()
            style.drawControl(
                QtWidgets.QStyle.ControlElement.CE_ItemViewItem,
                styled,
                painter,
                styled.widget,
            )

    class DataFrameModel(QtCore.QAbstractTableModel):
        def __init__(self, frame: pd.DataFrame | None = None, parent=None, language_getter=None):
            super().__init__(parent)
            self.frame = frame.copy() if frame is not None else pd.DataFrame()
            self.language_getter = language_getter or (lambda: "en_US")

        def rowCount(self, parent=QtCore.QModelIndex()):  # noqa: N802
            return 0 if parent.isValid() else len(self.frame)

        def columnCount(self, parent=QtCore.QModelIndex()):  # noqa: N802
            return 0 if parent.isValid() else len(self.frame.columns)

        def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
            if not index.isValid():
                return None
            if role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
                return QtCore.Qt.AlignmentFlag.AlignCenter
            if role != QtCore.Qt.ItemDataRole.DisplayRole:
                return None
            column = str(self.frame.columns[index.column()])
            value = display_value(self.language_getter(), column, self.frame.iloc[index.row(), index.column()])
            return format_value(column, value)

        def headerData(self, section, orientation, role=QtCore.Qt.ItemDataRole.DisplayRole):  # noqa: N802
            if role != QtCore.Qt.ItemDataRole.DisplayRole:
                return None
            if orientation == QtCore.Qt.Orientation.Horizontal:
                return display_column(self.language_getter(), str(self.frame.columns[section]))
            return str(section + 1)

        def refresh_language(self):
            if self.columnCount() > 0:
                self.headerDataChanged.emit(QtCore.Qt.Orientation.Horizontal, 0, self.columnCount() - 1)
            if self.rowCount() > 0 and self.columnCount() > 0:
                self.dataChanged.emit(
                    self.index(0, 0),
                    self.index(self.rowCount() - 1, self.columnCount() - 1),
                    [QtCore.Qt.ItemDataRole.DisplayRole],
                )

    class MainWindow(QtWidgets.QMainWindow):
        def __init__(self):
            super().__init__()
            self.language = DEFAULT_LANGUAGE
            self.resize(1500, 900)
            self.dataset: DataSet | None = None
            self.result = None
            self.current_path: Path | None = None
            self._models = []
            self._build_ui()
            self._apply_language()
            self.statusBar().showMessage(tr(self.language, "ready"))

        def _build_ui(self):
            root = QtWidgets.QWidget()
            self.setCentralWidget(root)
            outer = QtWidgets.QHBoxLayout(root)
            splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
            outer.addWidget(splitter)
            splitter.addWidget(self._controls())
            splitter.addWidget(self._workspace())
            splitter.setSizes([370, 1100])
            splitter.setStretchFactor(1, 1)

        def _controls(self):
            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            host = QtWidgets.QWidget()
            scroll.setWidget(host)
            v = QtWidgets.QVBoxLayout(host)

            self.language_box = QtWidgets.QGroupBox()
            language_form = QtWidgets.QFormLayout(self.language_box)
            self.language_combo = QtWidgets.QComboBox()
            self.language_combo.addItem("中文", "zh_CN")
            self.language_combo.addItem("English", "en_US")
            self.language_combo.setCurrentIndex(0)
            self.language_combo.currentIndexChanged.connect(self._change_language)
            language_form.addRow(self.language_combo)
            v.addWidget(self.language_box)

            self.data_box = QtWidgets.QGroupBox()
            lay = QtWidgets.QVBoxLayout(self.data_box)
            self.open_button = QtWidgets.QPushButton()
            self.open_button.clicked.connect(self.open_file)
            self.path_label = QtWidgets.QLabel()
            self.path_label.setWordWrap(True)
            self.meta_label = QtWidgets.QLabel("")
            lay.addWidget(self.open_button)
            lay.addWidget(self.path_label)
            lay.addWidget(self.meta_label)
            v.addWidget(self.data_box)

            self.eval_box = QtWidgets.QGroupBox()
            self.eval_form = QtWidgets.QFormLayout(self.eval_box)
            self.profile = QtWidgets.QComboBox()
            self.profile.currentIndexChanged.connect(self._sync_controls)
            self.eval_form.addRow("", self.profile)
            self.force = QtWidgets.QComboBox()
            self.eval_form.addRow("", self.force)
            self.window_percent = QtWidgets.QDoubleSpinBox()
            self.window_percent.setRange(0.1, 100)
            self.window_percent.setDecimals(2)
            self.window_percent.setValue(2)
            self.window_percent.setSuffix(" %")
            self.eval_form.addRow("", self.window_percent)
            self.window_basis = QtWidgets.QComboBox()
            self.eval_form.addRow("", self.window_basis)
            self.zero_target = QtWidgets.QDoubleSpinBox()
            self.zero_target.setRange(-1000, 1000)
            self.zero_target.setDecimals(2)
            self.zero_target.setSuffix(" mm")
            self.eval_form.addRow("", self.zero_target)
            v.addWidget(self.eval_box)

            self.gas_box = QtWidgets.QGroupBox()
            self.gas_form = QtWidgets.QFormLayout(self.gas_box)
            self.gas_mode = QtWidgets.QComboBox()
            self.gas_mode.currentIndexChanged.connect(self._sync_controls)
            self.gas_form.addRow("", self.gas_mode)
            self.gas_operation = QtWidgets.QComboBox()
            self.gas_form.addRow("", self.gas_operation)
            self.gas_force = QtWidgets.QDoubleSpinBox()
            self.gas_force.setRange(0, 10000)
            self.gas_force.setDecimals(2)
            self.gas_force.setSuffix(" N")
            self.gas_form.addRow("", self.gas_force)
            self.gas_pressure = QtWidgets.QDoubleSpinBox()
            self.gas_pressure.setRange(0, 30)
            self.gas_pressure.setDecimals(2)
            self.gas_pressure.setSuffix(" MPa(g)")
            self.gas_form.addRow("", self.gas_pressure)
            self.rod_dia = QtWidgets.QDoubleSpinBox()
            self.rod_dia.setRange(0, 100)
            self.rod_dia.setDecimals(2)
            self.rod_dia.setSuffix(" mm")
            self.gas_form.addRow("", self.rod_dia)
            v.addWidget(self.gas_box)

            self.analyze_button = QtWidgets.QPushButton()
            self.analyze_button.setMinimumHeight(38)
            self.analyze_button.clicked.connect(self.analyze)
            v.addWidget(self.analyze_button)

            self.plot_box = QtWidgets.QGroupBox()
            self.plot_form = QtWidgets.QFormLayout(self.plot_box)
            self.x_axis = QtWidgets.QComboBox()
            self.x_axis.currentIndexChanged.connect(self.refresh_plot)
            self.plot_form.addRow("", self.x_axis)
            self.y_axis = QtWidgets.QListWidget()
            self.y_axis.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.MultiSelection)
            self.y_axis.setItemDelegate(CurveColorItemDelegate(self.y_axis))
            self.y_axis.setMaximumHeight(150)
            self.y_axis.itemSelectionChanged.connect(self.refresh_plot)
            self.plot_form.addRow("", self.y_axis)
            self.current_filter = QtWidgets.QComboBox()
            self.current_filter.currentIndexChanged.connect(self._rebuild_runs)
            self.current_filter.currentIndexChanged.connect(self.refresh_plot)
            self.plot_form.addRow("", self.current_filter)
            self.run_filter = QtWidgets.QComboBox()
            self.run_filter.currentIndexChanged.connect(self._rebuild_cycles)
            self.run_filter.currentIndexChanged.connect(self.refresh_plot)
            self.plot_form.addRow("", self.run_filter)
            self.cycle_filter = QtWidgets.QComboBox()
            self.cycle_filter.currentIndexChanged.connect(self.refresh_plot)
            self.plot_form.addRow("", self.cycle_filter)
            v.addWidget(self.plot_box)

            self.export_box = QtWidgets.QGroupBox()
            h = QtWidgets.QHBoxLayout(self.export_box)
            self.excel_button = QtWidgets.QPushButton()
            self.excel_button.clicked.connect(self.export_excel)
            self.png_button = QtWidgets.QPushButton()
            self.png_button.clicked.connect(self.export_png)
            h.addWidget(self.excel_button)
            h.addWidget(self.png_button)
            v.addWidget(self.export_box)
            v.addStretch(1)
            self._sync_controls()
            return scroll

        def _workspace(self):
            self.tabs = QtWidgets.QTabWidget()
            self.plot_page = QtWidgets.QWidget()
            lay = QtWidgets.QVBoxLayout(self.plot_page)
            self.plot_area = pg.GraphicsLayoutWidget()
            lay.addWidget(self.plot_area)
            self.tabs.addTab(self.plot_page, "")
            self.summary_table = self._table()
            self.tabs.addTab(self.summary_table, "")
            self.run_table = self._table()
            self.tabs.addTab(self.run_table, "")
            self.cycle_table = self._table()
            self.tabs.addTab(self.cycle_table, "")
            return self.tabs

        def _table(self):
            table = QtWidgets.QTableView()
            table.setAlternatingRowColors(True)
            table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            return table

        @staticmethod
        def _set_combo_items(combo, items, selected_data=None):
            combo.blockSignals(True)
            combo.clear()
            for text, data in items:
                combo.addItem(text, data)
            index = combo.findData(selected_data)
            combo.setCurrentIndex(index if index >= 0 else 0)
            combo.blockSignals(False)

        def _set_form_label(self, form, field, text):
            label = form.labelForField(field)
            if label is not None:
                label.setText(text)

        def _change_language(self):
            self.language = self.language_combo.currentData() or DEFAULT_LANGUAGE
            self._apply_language()
            self._update_status_language()
            self.refresh_plot()

        def _apply_language(self):
            self.setWindowTitle(tr(self.language, "app_title"))
            self.language_box.setTitle(tr(self.language, "language_group"))
            self.data_box.setTitle(tr(self.language, "data_file"))
            self.open_button.setText(tr(self.language, "open_file"))
            self.eval_box.setTitle(tr(self.language, "evaluation"))
            self.gas_box.setTitle(tr(self.language, "gas_group"))
            self.plot_box.setTitle(tr(self.language, "plot_group"))
            self.export_box.setTitle(tr(self.language, "export"))
            self.analyze_button.setText(tr(self.language, "analyze"))
            self.excel_button.setText(tr(self.language, "excel"))
            self.png_button.setText(tr(self.language, "png"))

            profile_data = self.profile.currentData() or EvaluationProfile.AUDI.value
            self._set_combo_items(
                self.profile,
                [
                    (tr(self.language, "profile_audi"), EvaluationProfile.AUDI.value),
                    (tr(self.language, "profile_window"), EvaluationProfile.WINDOW_MEAN.value),
                    (tr(self.language, "profile_zero"), EvaluationProfile.ZERO_CROSSING.value),
                ],
                profile_data,
            )
            force_data = self.force.currentData() or "raw"
            self._set_combo_items(
                self.force,
                [(tr(self.language, "force_raw"), "raw"), (tr(self.language, "force_corrected"), "corrected")],
                force_data,
            )
            basis_data = self.window_basis.currentData() or "amplitude"
            self._set_combo_items(
                self.window_basis,
                [(tr(self.language, "basis_amplitude"), "amplitude"), (tr(self.language, "basis_total"), "total_stroke")],
                basis_data,
            )
            gas_data = self.gas_mode.currentData() or "off"
            self._set_combo_items(
                self.gas_mode,
                [
                    (tr(self.language, "gas_off"), "off"),
                    (tr(self.language, "gas_direct"), "direct"),
                    (tr(self.language, "gas_pressure_mode"), "pressure"),
                ],
                gas_data,
            )
            operation_data = self.gas_operation.currentData() or "subtract"
            self._set_combo_items(
                self.gas_operation,
                [
                    (tr(self.language, "gas_subtract"), "subtract"),
                    (tr(self.language, "gas_add"), "add"),
                ],
                operation_data,
            )

            for form, field, key in (
                (self.eval_form, self.profile, "profile"),
                (self.eval_form, self.force, "force"),
                (self.eval_form, self.window_percent, "window"),
                (self.eval_form, self.window_basis, "window_basis"),
                (self.eval_form, self.zero_target, "target_x"),
                (self.gas_form, self.gas_mode, "mode"),
                (self.gas_form, self.gas_operation, "gas_operation"),
                (self.gas_form, self.gas_force, "gas_force"),
                (self.gas_form, self.gas_pressure, "gauge_pressure"),
                (self.gas_form, self.rod_dia, "rod_diameter"),
                (self.plot_form, self.x_axis, "x_axis"),
                (self.plot_form, self.y_axis, "y_axis"),
                (self.plot_form, self.current_filter, "current"),
                (self.plot_form, self.run_filter, "run"),
                (self.plot_form, self.cycle_filter, "cycle"),
            ):
                self._set_form_label(form, field, tr(self.language, key))

            self.tabs.setTabText(self.tabs.indexOf(self.plot_page), tr(self.language, "tab_plot"))
            self.tabs.setTabText(self.tabs.indexOf(self.summary_table), tr(self.language, "tab_summary"))
            self.tabs.setTabText(self.tabs.indexOf(self.run_table), tr(self.language, "tab_run"))
            self.tabs.setTabText(self.tabs.indexOf(self.cycle_table), tr(self.language, "tab_cycle"))

            self._update_file_meta()
            self._translate_plot_controls()
            for model in self._models:
                refresh = getattr(model, "refresh_language", None)
                if callable(refresh):
                    refresh()
            self._sync_controls()

        def _translate_plot_controls(self):
            for i in range(self.x_axis.count()):
                channel = self.x_axis.itemData(i)
                if isinstance(channel, str):
                    self.x_axis.setItemText(i, display_channel(self.language, channel))
            for i in range(self.y_axis.count()):
                item = self.y_axis.item(i)
                channel = item.data(QtCore.Qt.ItemDataRole.UserRole)
                if isinstance(channel, str):
                    item.setText(display_channel(self.language, channel))
            for combo in (self.current_filter, self.run_filter, self.cycle_filter):
                for i in range(combo.count()):
                    if combo.itemData(i) is None:
                        combo.setItemText(i, tr(self.language, "all"))

        def _update_file_meta(self):
            if self.dataset is None:
                self.path_label.setText(tr(self.language, "no_file"))
                self.meta_label.setText("")
                return
            self.path_label.setText(str(self.current_path) if self.current_path else self.dataset.source_path.name)
            blocks = self.dataset.metadata.get("block_count", self.dataset.data["Block ID"].nunique())
            self.meta_label.setText(
                f"{tr(self.language, 'rows')}: {len(self.dataset.data):,}\n{tr(self.language, 'blocks')}: {blocks}"
            )

        def _update_status_language(self):
            if self.result is None:
                self.statusBar().showMessage(tr(self.language, "ready"))
                return
            warnings = int((self.result.runs["Status"] != "OK").sum()) if not self.result.runs.empty else 0
            self.statusBar().showMessage(
                tr(self.language, "analysis_complete").format(
                    runs=len(self.result.runs), cycles=len(self.result.cycles), warnings=warnings
                )
            )

        def _sync_controls(self):
            p = self.profile.currentData()
            self.window_percent.setEnabled(p == EvaluationProfile.WINDOW_MEAN.value)
            self.window_basis.setEnabled(p == EvaluationProfile.WINDOW_MEAN.value)
            self.zero_target.setEnabled(p == EvaluationProfile.ZERO_CROSSING.value)
            g = self.gas_mode.currentData()
            self.gas_operation.setEnabled(g != "off")
            self.gas_force.setEnabled(g == "direct")
            self.gas_pressure.setEnabled(g == "pressure")
            self.rod_dia.setEnabled(g == "pressure")

        def open_file(self):
            filename, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                tr(self.language, "open_test_data"),
                "",
                tr(self.language, "test_data_filter"),
            )
            if not filename:
                return
            try:
                self.dataset = load_test_data(filename)
            except Exception as exc:
                QtWidgets.QMessageBox.critical(self, tr(self.language, "import_error"), str(exc))
                return
            self.current_path = Path(filename)
            self._update_file_meta()
            self.analyze()

        def _config(self):
            return AnalyzerConfig(
                profile=EvaluationProfile(self.profile.currentData()),
                force_channel=self.force.currentData(),
                window_percent=float(self.window_percent.value()),
                window_basis=self.window_basis.currentData(),
                zero_target_mm=float(self.zero_target.value()),
                gas_mode=self.gas_mode.currentData(),
                gas_operation=self.gas_operation.currentData(),
                gas_force_n=float(self.gas_force.value()),
                gas_gauge_pressure_mpa=float(self.gas_pressure.value()),
                piston_rod_diameter_mm=float(self.rod_dia.value()),
            )

        def analyze(self):
            if self.dataset is None:
                return
            try:
                self.result = CDCAnalyzer(self._config()).analyze(self.dataset)
            except Exception as exc:
                QtWidgets.QMessageBox.critical(self, tr(self.language, "analysis_error"), str(exc))
                return
            for table, frame in (
                (self.summary_table, self.result.summary),
                (self.run_table, self.result.runs),
                (self.cycle_table, self.result.cycles),
            ):
                model = DataFrameModel(frame, table, language_getter=lambda: self.language)
                table.setModel(model)
                self._models.append(model)
            self._populate_plot_controls()
            self.refresh_plot()
            self._update_status_language()

        def _populate_plot_controls(self):
            channels = available_plot_channels(self.result.processed)
            dataset_changed = getattr(self, "_plot_controls_dataset", None) is not self.dataset
            imported_channels = [
                column
                for column in self.dataset.data.columns
                if column in channels and column not in {"Block ID", "Source Row"}
            ] if self.dataset is not None else []
            default_x = imported_channels[0] if imported_channels else (channels[0] if channels else None)
            default_y = set(imported_channels[1:])
            old_x = self.x_axis.currentData()
            self.x_axis.blockSignals(True)
            self.x_axis.clear()
            for channel in channels:
                self.x_axis.addItem(display_channel(self.language, channel), channel)
            target_x = default_x if dataset_changed else (old_x if old_x in channels else default_x)
            index = self.x_axis.findData(target_x)
            self.x_axis.setCurrentIndex(index if index >= 0 else 0)
            self.x_axis.blockSignals(False)

            old_y = {
                item.data(QtCore.Qt.ItemDataRole.UserRole)
                for item in self.y_axis.selectedItems()
                if item.data(QtCore.Qt.ItemDataRole.UserRole)
            }
            self.y_axis.blockSignals(True)
            self.y_axis.clear()
            selected_y = default_y if dataset_changed else old_y
            for channel in channels:
                item = QtWidgets.QListWidgetItem(display_channel(self.language, channel))
                item.setData(QtCore.Qt.ItemDataRole.UserRole, channel)
                self.y_axis.addItem(item)
                item.setSelected(channel in selected_y)
            self.y_axis.blockSignals(False)
            self._plot_controls_dataset = self.dataset

            old_current = self.current_filter.currentData()
            self.current_filter.blockSignals(True)
            self.current_filter.clear()
            self.current_filter.addItem(tr(self.language, "all"), None)
            for value in sorted(self.result.processed["Current Label"].dropna().unique().astype(float)):
                self.current_filter.addItem(f"{value:.1f} A", float(value))
            index = self.current_filter.findData(old_current)
            self.current_filter.setCurrentIndex(index if index >= 0 else 0)
            self.current_filter.blockSignals(False)
            self._rebuild_runs()

        def _rebuild_runs(self):
            old_run = self.run_filter.currentData()
            self.run_filter.blockSignals(True)
            self.run_filter.clear()
            self.run_filter.addItem(tr(self.language, "all"), None)
            if self.result is not None:
                rows = self.result.runs
                cur = self.current_filter.currentData()
                if cur is not None:
                    rows = rows[rows["Current Label A"].astype(float).round(1) == round(float(cur), 1)]
                for value in rows["Run ID"].dropna().astype(int):
                    self.run_filter.addItem(str(value), int(value))
            index = self.run_filter.findData(old_run)
            self.run_filter.setCurrentIndex(index if index >= 0 else 0)
            self.run_filter.blockSignals(False)
            self._rebuild_cycles()

        def _rebuild_cycles(self):
            old_cycle = self.cycle_filter.currentData()
            self.cycle_filter.blockSignals(True)
            self.cycle_filter.clear()
            self.cycle_filter.addItem(tr(self.language, "all"), None)
            if self.result is not None and self.run_filter.currentData() is not None:
                rows = self.result.cycles[
                    self.result.cycles["Run ID"].astype(int) == int(self.run_filter.currentData())
                ]
                for value in rows["Cycle ID"].dropna().astype(int):
                    self.cycle_filter.addItem(str(value), int(value))
            index = self.cycle_filter.findData(old_cycle)
            self.cycle_filter.setCurrentIndex(index if index >= 0 else 0)
            self.cycle_filter.blockSignals(False)

        def _selection(self):
            return PlotSelection(
                self.current_filter.currentData(),
                self.run_filter.currentData(),
                self.cycle_filter.currentData(),
            )

        def refresh_plot(self):
            if self.result is None or self.x_axis.currentData() is None:
                return
            ys = [
                item.data(QtCore.Qt.ItemDataRole.UserRole)
                for item in self.y_axis.selectedItems()
                if item.data(QtCore.Qt.ItemDataRole.UserRole)
            ]
            self._sync_y_axis_colors(ys)
            if not ys:
                return
            x = self.x_axis.currentData()
            data = filter_processed_data(self.result.processed, self._selection())
            self.plot_area.clear()
            if data.empty:
                return
            audi_overlay = (
                x == "Axial Displacement"
                and self.run_filter.currentData() is not None
                and self.result.settings.get("profile") == EvaluationProfile.AUDI.value
            )
            if same_units(ys):
                p = self.plot_area.addPlot(row=0, col=0)
                self._style_plot(p, x, ys[0])
                if len(ys) > 1:
                    p.addLegend()
                for i, y in enumerate(ys):
                    p.plot(
                        data[x].to_numpy(float),
                        data[y].to_numpy(float),
                        pen=pg.intColor(i, hues=max(1, len(ys))),
                        name=display_channel(self.language, y),
                    )
                force_y = next(
                    (y for y in ys if y in {"Axial Load", "Analysis Axial Load", "Corrected Axial Load"}),
                    None,
                )
                if audi_overlay and force_y:
                    self._overlay(p, force_y)
            else:
                previous = None
                for i, y in enumerate(ys):
                    p = self.plot_area.addPlot(row=i, col=0)
                    self._style_plot(p, x, y)
                    p.plot(data[x].to_numpy(float), data[y].to_numpy(float), pen=pg.intColor(i, hues=len(ys)))
                    if previous is not None:
                        p.setXLink(previous)
                    previous = p
                    if audi_overlay and y in {"Axial Load", "Analysis Axial Load", "Corrected Axial Load"}:
                        self._overlay(p, y)

        def _sync_y_axis_colors(self, selected_channels):
            """Show selected Y fields in the exact colors used by their curves."""
            colors = {
                channel: pg.intColor(index, hues=max(1, len(selected_channels)))
                for index, channel in enumerate(selected_channels)
            }
            default_brush = self.y_axis.palette().brush(
                self.y_axis.foregroundRole()
            )
            for index in range(self.y_axis.count()):
                item = self.y_axis.item(index)
                channel = item.data(QtCore.Qt.ItemDataRole.UserRole)
                item.setForeground(
                    pg.mkBrush(colors[channel]) if channel in colors else default_brush
                )

        def _style_plot(self, plot, x, y):
            plot.showGrid(x=True, y=True, alpha=.25)
            plot.setLabel("bottom", display_channel(self.language, x), units=unit_for_channel(x))
            plot.setLabel("left", display_channel(self.language, y), units=unit_for_channel(y))
            plot.setClipToView(True)
            plot.setDownsampling(auto=True, mode="peak")

        def _overlay(self, plot, force_col):
            ov = evaluation_overlay(self.result, self._selection(), force_col)
            if ov is None:
                return
            region = pg.LinearRegionItem(values=(ov.window_low_mm, ov.window_high_mm), movable=False)
            region.setZValue(-10)
            plot.addItem(region)
            spots = []
            if ov.rebound_x_mm is not None:
                spots.append({"pos": (ov.rebound_x_mm, ov.rebound_force_n), "symbol": "o", "size": 9})
            if ov.compression_x_mm is not None:
                spots.append({"pos": (ov.compression_x_mm, ov.compression_force_n), "symbol": "t", "size": 9})
            if spots:
                plot.addItem(pg.ScatterPlotItem(spots=spots))

        def export_excel(self):
            if self.result is None:
                return
            default = (self.current_path.stem + "_analyzed.xlsx") if self.current_path else "result.xlsx"
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, tr(self.language, "export_excel"), default, "Excel (*.xlsx)"
            )
            if filename:
                try:
                    out = export_xlsx(self.result, filename)
                    self.statusBar().showMessage(tr(self.language, "exported").format(path=out))
                except Exception as exc:
                    QtWidgets.QMessageBox.critical(self, tr(self.language, "export_error"), str(exc))

        def export_png(self):
            if self.result is None:
                return
            default = (self.current_path.stem + "_plot.png") if self.current_path else "plot.png"
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, tr(self.language, "export_plot"), default, "PNG (*.png)"
            )
            if filename:
                try:
                    export_plot_widget_png(self.plot_area, filename)
                    self.statusBar().showMessage(tr(self.language, "plot_exported").format(path=filename))
                except Exception as exc:
                    QtWidgets.QMessageBox.critical(self, tr(self.language, "export_error"), str(exc))

    return MainWindow


def main() -> int:
    _, QtWidgets, _ = _qt_imports()
    MainWindow = _build_gui_classes()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName("CDC Zero Position Force Analyzer")
    window = MainWindow()
    window.show()
    return int(app.exec())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
