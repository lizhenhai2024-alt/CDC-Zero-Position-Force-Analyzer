from __future__ import annotations

import sys

import pandas as pd

from .formatting import format_value
from .gui import _build_gui_classes, _qt_imports
from .i18n import display_column, display_value, tr
from .quality import build_block_quality, overall_quality_status
from .sweep import build_sweep_comparison


def _build_gui_classes_v04():
    QtCore, QtWidgets, _ = _qt_imports()
    BaseMainWindow = _build_gui_classes()

    class FrameModel(QtCore.QAbstractTableModel):
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

    class MainWindow(BaseMainWindow):
        def __init__(self):
            super().__init__()
            self.quality_frame = pd.DataFrame()
            self.quality_status = "Not checked"
            self.sweep_frame = pd.DataFrame()
            self.quality_table = self._table()
            self.sweep_table = self._table()
            if self.tabs is not None:
                self.tabs.addTab(self.sweep_table, "")
                self.tabs.addTab(self.quality_table, "")
            self._apply_v04_language()

        def _change_language(self):
            super()._change_language()
            self._apply_v04_language()

        def _apply_v04_language(self):
            if not hasattr(self, "tabs"):
                return
            if hasattr(self, "sweep_table"):
                self.tabs.setTabText(self.tabs.indexOf(self.sweep_table), tr(self.language, "tab_sweep"))
            if hasattr(self, "quality_table"):
                self.tabs.setTabText(self.tabs.indexOf(self.quality_table), tr(self.language, "tab_quality"))

        def _set_frame(self, table, frame: pd.DataFrame) -> None:
            model = FrameModel(frame, table, language_getter=lambda: self.language)
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

        def _update_status_language(self):
            if self.result is None:
                if getattr(self, "quality_status", "Not checked") == "Invalid" and self.dataset is not None:
                    self.statusBar().showMessage(tr(self.language, "analysis_blocked"))
                else:
                    self.statusBar().showMessage(tr(self.language, "ready"))
                return
            run_warnings = int((self.result.runs["Status"] != "OK").sum()) if not self.result.runs.empty else 0
            paired = int((self.sweep_frame.get("Coverage", pd.Series(dtype=str)) == "Up + Down").sum())
            quality = display_value(self.language, "Status", self.quality_status)
            self.statusBar().showMessage(
                tr(self.language, "analysis_complete_v04").format(
                    runs=len(self.result.runs),
                    cycles=len(self.result.cycles),
                    warnings=run_warnings,
                    quality=quality,
                    paired=paired,
                )
            )

        def analyze(self):
            if self.dataset is None:
                return
            quality_status = self._refresh_quality()
            if quality_status == "Invalid":
                self.result = None
                self.sweep_frame = pd.DataFrame()
                self._set_frame(self.sweep_table, self.sweep_frame)
                self.statusBar().showMessage(tr(self.language, "analysis_blocked"))
                QtWidgets.QMessageBox.critical(
                    self,
                    tr(self.language, "data_quality_error"),
                    tr(self.language, "data_quality_error_body"),
                )
                return

            super().analyze()
            if self.result is None:
                return
            self.sweep_frame = build_sweep_comparison(self.result.runs)
            self._set_frame(self.sweep_table, self.sweep_frame)
            self._update_status_language()

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
