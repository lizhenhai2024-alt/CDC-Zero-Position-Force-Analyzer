from __future__ import annotations

import html
import sys
from importlib.resources import files

from .gui import _qt_imports
from .gui_v05 import _build_gui_classes_v05, _help_html
from .product_info import (
    AUTHOR_DEPARTMENT_ZH,
    AUTHOR_NAME_ZH,
    COMPANY_EN,
    COMPANY_ZH,
    PRODUCT_NAME,
    RELEASE_DATE,
    RELEASE_EDITION_EN,
    RELEASE_EDITION_ZH,
)

OFFICIAL_WEBSITE = "https://www.faw-tokico.com/"


def _release_help_html(language: str) -> str:
    base = _help_html(language)
    if language == "zh_CN":
        old_title = "CDC 零位阻尼力分析器 — 专业帮助"
        new_title = f"{PRODUCT_NAME} — 专业帮助"
        release_box = f"""
        <div style="margin:8px 0 18px 0;padding:12px 14px;border:1px solid #bdbdbd;background:#f7f7f7;">
          <b>{html.escape(COMPANY_ZH)}</b><br>
          {html.escape(COMPANY_EN)}<br>
          编制：{html.escape(AUTHOR_DEPARTMENT_ZH)}　{html.escape(AUTHOR_NAME_ZH)}<br>
          发布日期：{html.escape(RELEASE_DATE)}　{html.escape(RELEASE_EDITION_ZH)}<br>
          公司官网：{html.escape(OFFICIAL_WEBSITE)}
        </div>
        """
        updated = base.replace("用于 CDC/电控减振器", "用于电控/半主动减振器")
    else:
        old_title = "CDC Zero Position Force Analyzer — Professional Help"
        new_title = f"{PRODUCT_NAME} — Professional Help"
        release_box = f"""
        <div style="margin:8px 0 18px 0;padding:12px 14px;border:1px solid #bdbdbd;background:#f7f7f7;">
          <b>{html.escape(COMPANY_EN)}</b><br>
          {html.escape(COMPANY_ZH)}<br>
          Prepared by: {html.escape(AUTHOR_DEPARTMENT_ZH)} / {html.escape(AUTHOR_NAME_ZH)}<br>
          Release date: {html.escape(RELEASE_DATE)}　{html.escape(RELEASE_EDITION_EN)}<br>
          Official website: {html.escape(OFFICIAL_WEBSITE)}
        </div>
        """
        updated = base.replace("CDC/electronic damper", "electronically controlled / semi-active damper")
    updated = updated.replace(old_title, new_title)
    marker = f"<h1>{new_title}</h1>"
    return updated.replace(marker, marker + release_box, 1)


def _find_app_icon():
    try:
        asset_dir = files("cdc_analyzer").joinpath("assets")
        for name in (
            "damper_test_data_analyzer.ico",
            "damper_test_data_analyzer.png",
            "damper_test_data_analyzer.svg",
        ):
            candidate = asset_dir.joinpath(name)
            if candidate.is_file():
                return str(candidate)
    except Exception:
        pass
    return None


def _build_release_gui_classes():
    QtCore, QtWidgets, _ = _qt_imports()
    from PySide6 import QtGui

    BaseMainWindow = _build_gui_classes_v05()

    class MainWindow(BaseMainWindow):
        def __init__(self):
            self.release_language_toolbar = None
            self.release_language_label = None
            self._initial_view_ranges: list[tuple[tuple[float, float], tuple[float, float]]] = []
            super().__init__()
            self._setup_language_toolbar()
            self._configure_release_defaults()
            self._ensure_plot_form_labels()
            self._style_plot_selectors()
            self._apply_release_identity()
            self._capture_initial_view_ranges()

        def _setup_language_toolbar(self):
            language_layout = self.language_box.layout()
            if language_layout is not None:
                language_layout.removeWidget(self.language_combo)
                language_layout.removeWidget(self.help_button)
            self.language_box.hide()

            toolbar = QtWidgets.QToolBar()
            toolbar.setObjectName("releaseLanguageToolbar")
            toolbar.setMovable(False)
            toolbar.setFloatable(False)
            toolbar.setMinimumHeight(46)
            toolbar.setContentsMargins(8, 3, 8, 3)

            label = QtWidgets.QLabel()
            label_font = label.font()
            label_font.setBold(True)
            label_font.setPointSize(max(10, label_font.pointSize()))
            label.setFont(label_font)
            label.setMinimumWidth(86)
            toolbar.addWidget(label)

            combo_font = self.language_combo.font()
            combo_font.setPointSize(max(10, combo_font.pointSize()))
            self.language_combo.setFont(combo_font)
            self.language_combo.setMinimumWidth(160)
            self.language_combo.setMinimumHeight(32)
            toolbar.addWidget(self.language_combo)

            spacer = QtWidgets.QWidget()
            spacer.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Preferred,
            )
            toolbar.addWidget(spacer)
            self.help_button.setMinimumHeight(32)
            toolbar.addWidget(self.help_button)
            self.addToolBar(QtCore.Qt.ToolBarArea.TopToolBarArea, toolbar)

            self.release_language_toolbar = toolbar
            self.release_language_label = label

        def _configure_release_defaults(self):
            index = self.window_basis.findData("total_stroke")
            if index >= 0:
                self.window_basis.setCurrentIndex(index)
            self.window_percent.setValue(2.0)
            self.window_basis.setToolTip("默认按总行程全宽定义评价窗口 / Default: total-stroke full width")

        def _ensure_plot_form_labels(self):
            self.plot_form.setLabelAlignment(
                QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
            )
            self.plot_form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            for field in (
                self.x_axis,
                self.y_axis,
                self.current_filter,
                self.run_filter,
                self.cycle_filter,
                self.background_combo,
            ):
                label = self.plot_form.labelForField(field)
                if label is not None:
                    label.setVisible(True)
                    label.setMinimumWidth(72)
                    font = label.font()
                    font.setBold(True)
                    label.setFont(font)

        def _style_plot_selectors(self):
            selection_style = (
                "QAbstractItemView::item:selected {"
                "background-color:#dff2df; color:#202020;"
                "}"
            )
            self.x_axis.view().setStyleSheet(selection_style)
            self.y_axis.setStyleSheet(
                "QListWidget::item:selected { background-color:#dff2df; color:#202020; }"
            )

        def _apply_v05_language(self):
            super()._apply_v05_language()
            if hasattr(self, "help_browser"):
                self._apply_release_identity()
            if getattr(self, "release_language_label", None) is not None:
                self.release_language_label.setText("界面语言" if self.language == "zh_CN" else "UI Language")
            if hasattr(self, "plot_form"):
                self._ensure_plot_form_labels()

        def _apply_release_identity(self):
            self.setWindowTitle(PRODUCT_NAME)
            icon_path = _find_app_icon()
            if icon_path:
                icon = QtGui.QIcon(icon_path)
                if not icon.isNull():
                    self.setWindowIcon(icon)
            if hasattr(self, "help_browser"):
                self.help_browser.setHtml(_release_help_html(self.language))
            if getattr(self, "release_language_label", None) is not None:
                self.release_language_label.setText("界面语言" if self.language == "zh_CN" else "UI Language")

        def refresh_plot(self):
            super().refresh_plot()
            if hasattr(self, "_initial_view_ranges"):
                self._capture_initial_view_ranges()

        def _capture_initial_view_ranges(self):
            plots = self._plot_items()
            if not plots:
                self._initial_view_ranges = []
                return
            for plot in plots:
                plot.enableAutoRange(x=True, y=True)
                plot.autoRange()
            self._initial_view_ranges = []
            for plot in plots:
                view_range = plot.viewRange()
                self._initial_view_ranges.append(
                    (
                        (float(view_range[0][0]), float(view_range[0][1])),
                        (float(view_range[1][0]), float(view_range[1][1])),
                    )
                )
                plot.getViewBox().disableAutoRange()

        def _reset_view(self):
            plots = self._plot_items()
            if not plots:
                return
            if len(self._initial_view_ranges) != len(plots):
                self._capture_initial_view_ranges()
            if len(self._initial_view_ranges) != len(plots):
                return
            for plot, (x_range, y_range) in zip(plots, self._initial_view_ranges):
                view_box = plot.getViewBox()
                view_box.disableAutoRange()
                view_box.setRange(xRange=x_range, yRange=y_range, padding=0)

    return MainWindow


def main() -> int:
    _, QtWidgets, _ = _qt_imports()
    MainWindow = _build_release_gui_classes()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName(PRODUCT_NAME)
    app.setOrganizationName(COMPANY_EN)
    window = MainWindow()
    window.show()
    return int(app.exec())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
