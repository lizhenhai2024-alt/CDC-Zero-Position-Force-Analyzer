from __future__ import annotations

import sys

from .gui import _qt_imports
from .gui_release_v072 import _build_release_gui_classes as _build_v072_classes
from .product_info import COMPANY_EN, PRODUCT_NAME


RESPONSE_PLOT_AREA_MIN_HEIGHT = 360
RESPONSE_TABLE_MIN_HEIGHT = 110
RESPONSE_TABLE_MAX_HEIGHT = 190


def _build_release_gui_classes():
    QtCore, QtWidgets, _ = _qt_imports()
    BaseMainWindow = _build_v072_classes()

    class MainWindow(BaseMainWindow):
        """V0.7.3 layout patch for response plots on ordinary laptop screens.

        V0.7.2 deliberately increased every response subplot minimum height to
        improve readability. On shorter screens that minimum was larger than the
        available tab height, so the bottom subplot (velocity in Event Detail,
        displacement in Full Overview) was clipped and its X axis / title could
        disappear below the visible area. V0.7.3 keeps the engineering axis
        margins but lets the three synchronized plots shrink evenly to the
        available viewport.
        """

        def __init__(self):
            super().__init__()
            self._configure_response_layout_v073()

        def _configure_response_layout_v073(self):
            controller = getattr(self, "dynamic_pages", None)
            if controller is None:
                return

            # The old 650 px plot-area minimum plus 3 x 235 px subplot minima
            # could exceed the available central-widget height. Keep a sensible
            # floor for usability, but allow the layout to fit common 768 px and
            # 900 px displays without clipping the third plot.
            controller.response_plot_area.setMinimumHeight(RESPONSE_PLOT_AREA_MIN_HEIGHT)
            controller.response_table.setMinimumHeight(RESPONSE_TABLE_MIN_HEIGHT)
            controller.response_table.setMaximumHeight(RESPONSE_TABLE_MAX_HEIGHT)

            splitter = controller.response_plot_area.parentWidget()
            if isinstance(splitter, QtWidgets.QSplitter):
                splitter.setChildrenCollapsible(False)
                splitter.setStretchFactor(0, 1)
                splitter.setStretchFactor(1, 0)
                splitter.setSizes([520, 145])

            self._fit_response_plots_v073()

        def _fit_response_plots_v073(self):
            plots = self._response_plot_items_v07()
            if not plots:
                return

            for plot in plots:
                # Cancel the inherited per-plot minimum (205/235 px). GraphicsLayout
                # will then divide the available height between all synchronized plots.
                plot.setMinimumHeight(0)
                plot.setMaximumHeight(16777215)

                bottom = plot.getAxis("bottom")
                bottom.show()
                bottom.setHeight(46)
                try:
                    bottom.setStyle(showValues=True)
                except TypeError:
                    pass

            # The bottom plot is the one most likely to be clipped. Explicitly
            # restore a visible X-axis title after every redraw.
            last_plot = plots[-1]
            last_plot.showAxis("bottom", True)
            last_plot.setLabel(
                "bottom",
                "时间" if self.language == "zh_CN" else "Time",
                units="s",
                **{"font-size": "11pt"},
            )

        def _draw_response_detail_v07(self):
            super()._draw_response_detail_v07()
            plots = self._response_plot_items_v07()
            if plots:
                # Detail mode is always Current / Force / Velocity in V0.7.2+.
                plots[-1].setTitle(
                    "速度" if self.language == "zh_CN" else "Velocity",
                    size="11pt",
                )
            self._fit_response_plots_v073()

        def _draw_response_overview(self):
            super()._draw_response_overview()
            self._fit_response_plots_v073()

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
