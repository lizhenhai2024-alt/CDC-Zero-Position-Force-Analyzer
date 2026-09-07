from __future__ import annotations

import sys

import pandas as pd

from .formatting import format_value
from .gui import _build_gui_classes, _qt_imports
from .quality import build_block_quality, overall_quality_status
from .sweep import build_sweep_comparison


def _build_gui_classes_v04():
    QtCore, QtWidgets, _ = _qt_imports()
    BaseMainWindow = _build_gui_classes()

    class FrameModel(QtCore.QAbstractTableModel):
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

    class MainWindow(BaseMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("CDC Zero Position Force Analyzer v0.4")
            self.quality_frame = pd.DataFrame()
            self.quality_status = "Not checked"
            self.sweep_frame = pd.DataFrame()
            self.quality_table = self._table()
            self.sweep_table = self._table()
            tabs = self.centralWidget().findChild(QtWidgets.QTabWidget)
            if tabs is not None:
                tabs.addTab(self.sweep_table, "Sweep Comparison")
                tabs.addTab(self.quality_table, "Data Quality")

        def _set_frame(self, table, frame: pd.DataFrame) -> None:
            model = FrameModel(frame, table)
            table.setModel(model)
            self._models.append(model)

        def _refresh_quality(self) -> str:
            if self.dataset is None:
                self.quality_frame = pd.DataFrame()
                self.quality_status = "Invalid"
            else:
                self.quality_frame = build_block_quality(self.dataset.data)
                self.quality_status = overall_quality_status(self.quality_frame)
            self._set_frame(self.quality_table, self.quality_frame)
            return self.quality_status

        def analyze(self):
            if self.dataset is None:
                return
            quality_status = self._refresh_quality()
            if quality_status == "Invalid":
                self.result = None
                self.sweep_frame = pd.DataFrame()
                self._set_frame(self.sweep_table, self.sweep_frame)
                self.statusBar().showMessage("Analysis blocked: raw-data quality is Invalid")
                QtWidgets.QMessageBox.critical(
                    self,
                    "Data quality error",
                    "Raw-data preflight found a structural error. Open the Data Quality tab for details before analysis.",
                )
                return

            super().analyze()
            if self.result is None:
                return
            self.sweep_frame = build_sweep_comparison(self.result.runs)
            self._set_frame(self.sweep_table, self.sweep_frame)
            run_warnings = int((self.result.runs["Status"] != "OK").sum()) if not self.result.runs.empty else 0
            paired = int((self.sweep_frame.get("Coverage", pd.Series(dtype=str)) == "Up + Down").sum())
            self.statusBar().showMessage(
                f"Analysis complete: {len(self.result.runs)} runs, {len(self.result.cycles)} complete cycles, "
                f"{run_warnings} run warnings | Data quality: {quality_status} | {paired} paired sweep levels"
            )

    return MainWindow


def main() -> int:
    _, QtWidgets, _ = _qt_imports()
    MainWindow = _build_gui_classes_v04()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName("CDC Zero Position Force Analyzer")
    window = MainWindow()
    window.show()
    return int(app.exec())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
