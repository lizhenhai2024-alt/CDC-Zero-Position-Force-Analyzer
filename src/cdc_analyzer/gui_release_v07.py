from __future__ import annotations

import sys

import numpy as np

from .dynamic_analysis import CURRENT, DISP, LOAD, TIME
from .gui import _qt_imports
from .gui_release import _build_release_gui_classes as _build_v06_classes
from .gui_release import _release_help_html
from .product_info import COMPANY_EN, PRODUCT_NAME


def _help_html_v07(language: str) -> str:
    text = _release_help_html(language)
    if language == "zh_CN":
        return text.replace("专业帮助", "帮助")
    return text.replace("Professional Help", "Help")


def _build_release_gui_classes():
    QtCore, QtWidgets, _ = _qt_imports()
    BaseMainWindow = _build_v06_classes()

    class MainWindow(BaseMainWindow):
        def __init__(self):
            self._v07_ready = False
            self._v07_toolbar_spacer = None
            self._v07_response_base_refresh = None
            self.response_view_label = None
            self.response_view_mode = None
            super().__init__()
            self._configure_v07_toolbar()
            self._configure_v07_response_overview()
            self._v07_ready = True
            self._apply_v07_language()

        def _configure_v07_toolbar(self):
            toolbar = self.release_language_toolbar
            if toolbar is None:
                return

            # The V0.6 toolbar order was Language -> spacer -> Help.
            # Keep the original widgets alive, hide the old spacer/help, and
            # insert a new expanding spacer before Language so the selector
            # occupies the former Help-button position on the right.
            for action in toolbar.actions():
                widget = toolbar.widgetForAction(action)
                if widget is None:
                    continue
                if widget not in (self.release_language_label, self.language_combo, self.help_button):
                    widget.hide()
            self.help_button.hide()

            spacer = QtWidgets.QWidget()
            spacer.setObjectName("v07LanguageToolbarSpacer")
            spacer.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Preferred,
            )
            actions = toolbar.actions()
            if actions:
                toolbar.insertWidget(actions[0], spacer)
            else:
                toolbar.addWidget(spacer)
            self._v07_toolbar_spacer = spacer

            self.release_language_label.setMinimumWidth(44)
            self.language_combo.setMinimumWidth(160)
            self.help_button.setVisible(False)

        def _configure_v07_response_overview(self):
            controller = getattr(self, "dynamic_pages", None)
            if controller is None:
                return

            row_widget = QtWidgets.QWidget(controller.response_page)
            row = QtWidgets.QHBoxLayout(row_widget)
            row.setContentsMargins(0, 0, 0, 0)
            label = QtWidgets.QLabel(row_widget)
            mode = QtWidgets.QComboBox(row_widget)
            mode.addItem("", "detail")
            mode.addItem("", "overview")
            mode.setMinimumWidth(230)
            row.addWidget(label)
            row.addWidget(mode)
            row.addStretch(1)

            root = controller.response_page.layout()
            root.insertWidget(2, row_widget)
            self.response_view_label = label
            self.response_view_mode = mode

            self._v07_response_base_refresh = controller.refresh_response_plot
            try:
                controller.response_event_combo.currentIndexChanged.disconnect()
            except (TypeError, RuntimeError):
                pass
            controller.response_event_combo.currentIndexChanged.connect(self._refresh_response_v07)
            mode.currentIndexChanged.connect(self._refresh_response_v07)
            # Internal controller calls (analysis/background refresh) now honor the selected view.
            controller.refresh_response_plot = self._refresh_response_v07

        def _refresh_response_v07(self, *_args):
            if self.response_view_mode is not None and self.response_view_mode.currentData() == "overview":
                self._draw_response_overview()
            elif self._v07_response_base_refresh is not None:
                self._v07_response_base_refresh()

        def _draw_response_overview(self):
            controller = getattr(self, "dynamic_pages", None)
            if controller is None or controller.response_result is None:
                return
            data = controller.response_result.processed.copy()
            if data.empty:
                return
            data = data.sort_values(TIME)
            plot_area = controller.response_plot_area
            plot_area.clear()
            t = data[TIME].to_numpy(float)

            specifications = (
                (LOAD, self._text_v07("阻尼力（复原 + / 压缩 -）", "Damping force (Rebound + / Compression -)"), "N"),
                (CURRENT, self._text_v07("阀电流", "Valve current"), "A"),
                (DISP, self._text_v07("位移", "Displacement"), "mm"),
            )
            previous = None
            plots = []
            for row_index, (column, label, unit) in enumerate(specifications):
                plot = plot_area.addPlot(row=row_index, col=0)
                controller._axis_style(plot, label, unit)
                plot.setMinimumHeight(225)
                plot.plot(t, data[column].to_numpy(float), pen=controller._curve_pen(2.5))
                if previous is not None:
                    plot.setXLink(previous)
                previous = plot
                plots.append(plot)

            plots[0].setTitle(
                self._text_v07("响应时间试验全流程总览（Audi 图15风格）", "Full response-test overview (Audi Fig. 15 style)"),
                size="12pt",
            )

            events = controller.response_result.events
            if not events.empty:
                force_values = data[LOAD].to_numpy(float)
                current_values = data[CURRENT].to_numpy(float)
                force_top = float(np.nanmax(force_values)) if len(force_values) else 0.0
                current_top = float(np.nanmax(current_values)) if len(current_values) else 0.0
                for _, event in events.iterrows():
                    event_time = float(event.get("t0 s", np.nan))
                    if not np.isfinite(event_time):
                        continue
                    for plot in plots:
                        controller._add_vertical_marker(plot, event_time)
                    stage = controller._display_value("Stage", event.get("Stage", ""))
                    direction = controller._display_value("Direction", event.get("Direction", ""))
                    event_id = int(event.get("Event ID", 0))
                    controller._add_intersection(
                        plots[1],
                        event_time,
                        float(event.get("Trigger Current A", current_top)),
                        f"E{event_id}",
                    )
                    plots[0].addItem(
                        controller._text_item(
                            f"E{event_id}  {stage}  {direction}",
                            event_time,
                            force_top,
                            anchor=(0, 0),
                        )
                    )

        def _text_v07(self, zh: str, en: str) -> str:
            return zh if self.language == "zh_CN" else en

        def _apply_v05_language(self):
            super()._apply_v05_language()
            if getattr(self, "_v07_ready", False):
                self._apply_v07_language()

        def _apply_v07_language(self):
            if self.release_language_label is not None:
                self.release_language_label.setText("语言" if self.language == "zh_CN" else "Language")
            self.help_button.setVisible(False)
            help_index = self.tabs.indexOf(self.help_page)
            if help_index >= 0:
                self.tabs.setTabText(help_index, "帮助" if self.language == "zh_CN" else "Help")
            self.help_browser.setHtml(_help_html_v07(self.language))

            if self.response_view_label is not None and self.response_view_mode is not None:
                self.response_view_label.setText("图形视图" if self.language == "zh_CN" else "Plot view")
                self.response_view_mode.setItemText(
                    self.response_view_mode.findData("detail"),
                    "阶段详情" if self.language == "zh_CN" else "Event detail",
                )
                self.response_view_mode.setItemText(
                    self.response_view_mode.findData("overview"),
                    "全流程总览（Audi图15）" if self.language == "zh_CN" else "Full overview (Audi Fig. 15)",
                )
            self._refresh_response_v07()

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
