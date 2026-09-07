from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from .analysis import AnalyzerConfig, CDCAnalyzer, EvaluationProfile
from .export import export_xlsx
from .formatting import format_value
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

    class DataFrameModel(QtCore.QAbstractTableModel):
        def __init__(self, frame: pd.DataFrame | None = None, parent=None):
            super().__init__(parent)
            self.frame = frame.copy() if frame is not None else pd.DataFrame()

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
            return format_value(column, self.frame.iloc[index.row(), index.column()])

        def headerData(self, section, orientation, role=QtCore.Qt.ItemDataRole.DisplayRole):  # noqa: N802
            if role != QtCore.Qt.ItemDataRole.DisplayRole:
                return None
            return str(self.frame.columns[section]) if orientation == QtCore.Qt.Orientation.Horizontal else str(section + 1)

    class MainWindow(QtWidgets.QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("CDC Zero Position Force Analyzer v0.2")
            self.resize(1500, 900)
            self.dataset: DataSet | None = None
            self.result = None
            self.current_path: Path | None = None
            self._models = []
            self._build_ui()
            self.statusBar().showMessage("Ready")

        def _build_ui(self):
            root = QtWidgets.QWidget()
            self.setCentralWidget(root)
            outer = QtWidgets.QHBoxLayout(root)
            splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
            outer.addWidget(splitter)
            splitter.addWidget(self._controls())
            splitter.addWidget(self._workspace())
            splitter.setSizes([360, 1100])
            splitter.setStretchFactor(1, 1)

        def _controls(self):
            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            host = QtWidgets.QWidget()
            scroll.setWidget(host)
            v = QtWidgets.QVBoxLayout(host)

            box = QtWidgets.QGroupBox("Data file")
            lay = QtWidgets.QVBoxLayout(box)
            btn = QtWidgets.QPushButton("Open DAT / CSV / XLSX")
            btn.clicked.connect(self.open_file)
            self.path_label = QtWidgets.QLabel("No file loaded")
            self.path_label.setWordWrap(True)
            self.meta_label = QtWidgets.QLabel("")
            lay.addWidget(btn); lay.addWidget(self.path_label); lay.addWidget(self.meta_label)
            v.addWidget(box)

            box = QtWidgets.QGroupBox("Evaluation")
            form = QtWidgets.QFormLayout(box)
            self.profile = QtWidgets.QComboBox()
            self.profile.addItem("Audi — Last cycle / 10% stroke / Peak", EvaluationProfile.AUDI.value)
            self.profile.addItem("Window Mean", EvaluationProfile.WINDOW_MEAN.value)
            self.profile.addItem("Zero Crossing", EvaluationProfile.ZERO_CROSSING.value)
            self.profile.currentIndexChanged.connect(self._sync_controls)
            form.addRow("Profile", self.profile)
            self.force = QtWidgets.QComboBox()
            self.force.addItem("Measured load", "raw"); self.force.addItem("Gas-corrected load", "corrected")
            form.addRow("Force", self.force)
            self.window_percent = QtWidgets.QDoubleSpinBox(); self.window_percent.setRange(0.1, 100); self.window_percent.setDecimals(2); self.window_percent.setValue(2); self.window_percent.setSuffix(" %")
            form.addRow("Window", self.window_percent)
            self.window_basis = QtWidgets.QComboBox(); self.window_basis.addItem("Single-sided amplitude", "amplitude"); self.window_basis.addItem("Total-stroke full width", "total_stroke")
            form.addRow("Window basis", self.window_basis)
            self.zero_target = QtWidgets.QDoubleSpinBox(); self.zero_target.setRange(-1000, 1000); self.zero_target.setDecimals(2); self.zero_target.setSuffix(" mm")
            form.addRow("Target X", self.zero_target)
            v.addWidget(box)

            box = QtWidgets.QGroupBox("Gas rebound-force correction")
            form = QtWidgets.QFormLayout(box)
            self.gas_mode = QtWidgets.QComboBox(); self.gas_mode.addItem("Off", "off"); self.gas_mode.addItem("Direct force", "direct"); self.gas_mode.addItem("Pressure + rod diameter", "pressure")
            self.gas_mode.currentIndexChanged.connect(self._sync_controls)
            form.addRow("Mode", self.gas_mode)
            self.gas_force = QtWidgets.QDoubleSpinBox(); self.gas_force.setRange(0, 10000); self.gas_force.setDecimals(2); self.gas_force.setSuffix(" N")
            form.addRow("Gas force", self.gas_force)
            self.gas_pressure = QtWidgets.QDoubleSpinBox(); self.gas_pressure.setRange(0, 30); self.gas_pressure.setDecimals(2); self.gas_pressure.setSuffix(" MPa(g)")
            form.addRow("Gauge pressure", self.gas_pressure)
            self.rod_dia = QtWidgets.QDoubleSpinBox(); self.rod_dia.setRange(0, 100); self.rod_dia.setDecimals(2); self.rod_dia.setSuffix(" mm")
            form.addRow("Rod diameter", self.rod_dia)
            v.addWidget(box)

            btn = QtWidgets.QPushButton("Analyze"); btn.setMinimumHeight(38); btn.clicked.connect(self.analyze); v.addWidget(btn)

            box = QtWidgets.QGroupBox("Plot")
            form = QtWidgets.QFormLayout(box)
            self.x_axis = QtWidgets.QComboBox(); self.x_axis.currentIndexChanged.connect(self.refresh_plot); form.addRow("X axis", self.x_axis)
            self.y_axis = QtWidgets.QListWidget(); self.y_axis.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.MultiSelection); self.y_axis.setMaximumHeight(150); self.y_axis.itemSelectionChanged.connect(self.refresh_plot); form.addRow("Y axis", self.y_axis)
            self.current_filter = QtWidgets.QComboBox(); self.current_filter.currentIndexChanged.connect(self._rebuild_runs); self.current_filter.currentIndexChanged.connect(self.refresh_plot); form.addRow("Current", self.current_filter)
            self.run_filter = QtWidgets.QComboBox(); self.run_filter.currentIndexChanged.connect(self._rebuild_cycles); self.run_filter.currentIndexChanged.connect(self.refresh_plot); form.addRow("Run", self.run_filter)
            self.cycle_filter = QtWidgets.QComboBox(); self.cycle_filter.currentIndexChanged.connect(self.refresh_plot); form.addRow("Cycle", self.cycle_filter)
            v.addWidget(box)

            box = QtWidgets.QGroupBox("Export")
            h = QtWidgets.QHBoxLayout(box)
            b1 = QtWidgets.QPushButton("Excel"); b1.clicked.connect(self.export_excel)
            b2 = QtWidgets.QPushButton("PNG"); b2.clicked.connect(self.export_png)
            h.addWidget(b1); h.addWidget(b2); v.addWidget(box); v.addStretch(1)
            self._sync_controls()
            return scroll

        def _workspace(self):
            tabs = QtWidgets.QTabWidget()
            page = QtWidgets.QWidget(); lay = QtWidgets.QVBoxLayout(page); self.plot_area = pg.GraphicsLayoutWidget(); lay.addWidget(self.plot_area); tabs.addTab(page, "Plot")
            self.summary_table = self._table(); tabs.addTab(self.summary_table, "Summary")
            self.run_table = self._table(); tabs.addTab(self.run_table, "Run Detail")
            self.cycle_table = self._table(); tabs.addTab(self.cycle_table, "Cycle Detail")
            return tabs

        def _table(self):
            table = QtWidgets.QTableView(); table.setAlternatingRowColors(True); table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents); return table

        def _sync_controls(self):
            p = self.profile.currentData()
            self.window_percent.setEnabled(p == EvaluationProfile.WINDOW_MEAN.value); self.window_basis.setEnabled(p == EvaluationProfile.WINDOW_MEAN.value); self.zero_target.setEnabled(p == EvaluationProfile.ZERO_CROSSING.value)
            g = self.gas_mode.currentData(); self.gas_force.setEnabled(g == "direct"); self.gas_pressure.setEnabled(g == "pressure"); self.rod_dia.setEnabled(g == "pressure")

        def open_file(self):
            filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open test data", "", "Test data (*.dat *.csv *.xlsx *.xlsm);;All files (*)")
            if not filename: return
            try: self.dataset = load_test_data(filename)
            except Exception as exc: QtWidgets.QMessageBox.critical(self, "Import error", str(exc)); return
            self.current_path = Path(filename); self.path_label.setText(filename)
            self.meta_label.setText(f"Rows: {len(self.dataset.data):,}\nBlocks: {self.dataset.metadata.get('block_count', self.dataset.data['Block ID'].nunique())}")
            self.analyze()

        def _config(self):
            return AnalyzerConfig(profile=EvaluationProfile(self.profile.currentData()), force_channel=self.force.currentData(), window_percent=float(self.window_percent.value()), window_basis=self.window_basis.currentData(), zero_target_mm=float(self.zero_target.value()), gas_mode=self.gas_mode.currentData(), gas_force_n=float(self.gas_force.value()), gas_gauge_pressure_mpa=float(self.gas_pressure.value()), piston_rod_diameter_mm=float(self.rod_dia.value()))

        def analyze(self):
            if self.dataset is None: return
            try: self.result = CDCAnalyzer(self._config()).analyze(self.dataset)
            except Exception as exc: QtWidgets.QMessageBox.critical(self, "Analysis error", str(exc)); return
            for table, frame in ((self.summary_table, self.result.summary), (self.run_table, self.result.runs), (self.cycle_table, self.result.cycles)):
                model = DataFrameModel(frame, table); table.setModel(model); self._models.append(model)
            self._populate_plot_controls(); self.refresh_plot()
            warnings = int((self.result.runs["Status"] != "OK").sum()) if not self.result.runs.empty else 0
            self.statusBar().showMessage(f"Analysis complete: {len(self.result.runs)} runs, {len(self.result.cycles)} complete cycles, {warnings} warnings")

        def _populate_plot_controls(self):
            channels = available_plot_channels(self.result.processed)
            self.x_axis.blockSignals(True); self.x_axis.clear(); self.x_axis.addItems(channels); self.x_axis.setCurrentText("Axial Displacement"); self.x_axis.blockSignals(False)
            self.y_axis.blockSignals(True); self.y_axis.clear()
            for c in channels:
                item = QtWidgets.QListWidgetItem(c); self.y_axis.addItem(item); item.setSelected(c == "Axial Load")
            self.y_axis.blockSignals(False)
            self.current_filter.blockSignals(True); self.current_filter.clear(); self.current_filter.addItem("All", None)
            for x in sorted(self.result.processed["Current Label"].dropna().unique().astype(float)): self.current_filter.addItem(f"{x:.1f} A", float(x))
            self.current_filter.blockSignals(False); self._rebuild_runs()

        def _rebuild_runs(self):
            self.run_filter.blockSignals(True); self.run_filter.clear(); self.run_filter.addItem("All", None)
            if self.result is not None:
                rows = self.result.runs; cur = self.current_filter.currentData()
                if cur is not None: rows = rows[rows["Current Label A"].astype(float).round(1) == round(float(cur), 1)]
                for x in rows["Run ID"].dropna().astype(int): self.run_filter.addItem(str(x), int(x))
            self.run_filter.blockSignals(False); self._rebuild_cycles()

        def _rebuild_cycles(self):
            self.cycle_filter.blockSignals(True); self.cycle_filter.clear(); self.cycle_filter.addItem("All", None)
            if self.result is not None and self.run_filter.currentData() is not None:
                rows = self.result.cycles[self.result.cycles["Run ID"].astype(int) == int(self.run_filter.currentData())]
                for x in rows["Cycle ID"].dropna().astype(int): self.cycle_filter.addItem(str(x), int(x))
            self.cycle_filter.blockSignals(False)

        def _selection(self):
            return PlotSelection(self.current_filter.currentData(), self.run_filter.currentData(), self.cycle_filter.currentData())

        def refresh_plot(self):
            if self.result is None or not self.x_axis.currentText(): return
            ys = [x.text() for x in self.y_axis.selectedItems()]
            if not ys: return
            x = self.x_axis.currentText(); data = filter_processed_data(self.result.processed, self._selection()); self.plot_area.clear()
            if data.empty: return
            audi_overlay = x == "Axial Displacement" and self.run_filter.currentData() is not None and self.result.settings.get("profile") == EvaluationProfile.AUDI.value
            if same_units(ys):
                p = self.plot_area.addPlot(row=0, col=0); self._style_plot(p, x, ys[0])
                if len(ys) > 1: p.addLegend()
                for i, y in enumerate(ys): p.plot(data[x].to_numpy(float), data[y].to_numpy(float), pen=pg.intColor(i, hues=max(1, len(ys))), name=y)
                force_y = next((y for y in ys if y in {"Axial Load", "Analysis Axial Load", "Corrected Axial Load"}), None)
                if audi_overlay and force_y: self._overlay(p, force_y)
            else:
                previous = None
                for i, y in enumerate(ys):
                    p = self.plot_area.addPlot(row=i, col=0); self._style_plot(p, x, y); p.plot(data[x].to_numpy(float), data[y].to_numpy(float), pen=pg.intColor(i, hues=len(ys)))
                    if previous is not None: p.setXLink(previous)
                    previous = p
                    if audi_overlay and y in {"Axial Load", "Analysis Axial Load", "Corrected Axial Load"}: self._overlay(p, y)

        def _style_plot(self, plot, x, y):
            plot.showGrid(x=True, y=True, alpha=.25); plot.setLabel("bottom", x, units=unit_for_channel(x)); plot.setLabel("left", y, units=unit_for_channel(y)); plot.setClipToView(True); plot.setDownsampling(auto=True, mode="peak")

        def _overlay(self, plot, force_col):
            ov = evaluation_overlay(self.result, self._selection(), force_col)
            if ov is None: return
            region = pg.LinearRegionItem(values=(ov.window_low_mm, ov.window_high_mm), movable=False); region.setZValue(-10); plot.addItem(region)
            spots = []
            if ov.rebound_x_mm is not None: spots.append({"pos": (ov.rebound_x_mm, ov.rebound_force_n), "symbol": "o", "size": 9})
            if ov.compression_x_mm is not None: spots.append({"pos": (ov.compression_x_mm, ov.compression_force_n), "symbol": "t", "size": 9})
            if spots: plot.addItem(pg.ScatterPlotItem(spots=spots))

        def export_excel(self):
            if self.result is None: return
            default = (self.current_path.stem + "_analyzed.xlsx") if self.current_path else "result.xlsx"
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export Excel", default, "Excel (*.xlsx)")
            if filename:
                try: out = export_xlsx(self.result, filename); self.statusBar().showMessage(f"Exported: {out}")
                except Exception as exc: QtWidgets.QMessageBox.critical(self, "Export error", str(exc))

        def export_png(self):
            if self.result is None: return
            default = (self.current_path.stem + "_plot.png") if self.current_path else "plot.png"
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export plot", default, "PNG (*.png)")
            if filename:
                try:
                    import pyqtgraph.exporters
                    pyqtgraph.exporters.ImageExporter(self.plot_area.scene()).export(filename)
                    self.statusBar().showMessage(f"Plot exported: {filename}")
                except Exception as exc: QtWidgets.QMessageBox.critical(self, "Export error", str(exc))

    return MainWindow


def main() -> int:
    _, QtWidgets, _ = _qt_imports()
    MainWindow = _build_gui_classes()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName("CDC Zero Position Force Analyzer")
    window = MainWindow(); window.show()
    return int(app.exec())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
