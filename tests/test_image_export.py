from PIL import Image
import pytest

from cdc_analyzer.image_export import (
    DEFAULT_PNG_EXPORT_PPI,
    export_plot_widget_png,
    export_width_for_ppi,
    set_png_ppi,
)


def test_png_export_writes_selected_ppi_metadata_and_print_resolution(tmp_path):
    output = tmp_path / "plot.png"
    Image.new("RGB", (20, 20), "white").save(output)

    set_png_ppi(output)
    with Image.open(output) as image:
        assert image.info["dpi"] == pytest.approx(
            (DEFAULT_PNG_EXPORT_PPI, DEFAULT_PNG_EXPORT_PPI), abs=0.1
        )

    set_png_ppi(output, 600)
    with Image.open(output) as image:
        assert image.info["dpi"] == pytest.approx((600, 600), abs=0.1)

    assert export_width_for_ppi(800, 600) == 5000
    assert export_width_for_ppi(1920, 600) == 12000
    assert export_width_for_ppi(800, 300) == 2500


def test_pyqtgraph_chart_export_uses_selected_ppi(tmp_path):
    pytest.importorskip("PySide6")
    pg = pytest.importorskip("pyqtgraph")
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    widget = pg.GraphicsLayoutWidget()
    widget.resize(400, 240)
    plot = widget.addPlot()
    plot.plot([0, 1], [0, 1])
    widget.show()
    app.processEvents()

    output = export_plot_widget_png(widget, tmp_path / "chart.png", ppi=300)
    with Image.open(output) as image:
        assert image.info["dpi"] == pytest.approx((300, 300), abs=0.1)
        assert image.width >= 2500
    widget.close()
