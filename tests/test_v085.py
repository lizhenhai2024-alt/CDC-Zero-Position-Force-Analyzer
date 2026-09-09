from pathlib import Path
import os

import numpy as np
import pandas as pd
import pytest

from cdc_analyzer.dynamic_analysis import TIME, CURRENT, LOAD, DISP, HysteresisConfig, HysteresisStandard
from cdc_analyzer.parser import DataSet
from cdc_analyzer.hysteresis_v085 import analyze_hysteresis_v085, speed_groups


def multi_speed_data():
    blocks = []
    for speed in (0.1, 0.3, 0.6, 1.0):
        for current, down in ((0.3, False), (0.8, False), (1.6, False), (0.8, True), (0.3, True)):
            block_id = len(blocks) + 1
            t = np.linspace(0, 7, 2801)
            amplitude = speed * 1000 / (2 * np.pi)
            x = -amplitude * np.cos(2 * np.pi * t)
            magnitude = 1000 * speed * (1 + current) + (20 if down else 0)
            force = np.where(np.sin(2 * np.pi * t) >= 0, magnitude, -magnitude * 1.2)
            blocks.append(pd.DataFrame({TIME: t + block_id * 10, DISP: x, CURRENT: current, LOAD: force, "Block ID": block_id}))
    return DataSet(pd.concat(blocks, ignore_index=True), Path("multi_speed.dat"), "synthetic")


@pytest.mark.parametrize("standard", [HysteresisStandard.BMW, HysteresisStandard.AUDI])
def test_hysteresis_separates_speeds_and_does_not_average_them(standard):
    result = analyze_hysteresis_v085(multi_speed_data(), HysteresisConfig(standard=standard))
    assert result.runs["Speed Group m/s"].nunique() == 4
    assert result.summary["Speed Group m/s"].nunique() == 4
    rebound = result.summary[result.summary["Direction"] == "Rebound"]
    if standard == HysteresisStandard.BMW:
        rebound = rebound[rebound["Current A"] == 0.8]
    assert len(rebound) == 4
    assert rebound["Hysteresis N"].to_numpy() == pytest.approx([20] * 4, abs=1)


def test_speed_groups_do_not_chain_distinct_conditions():
    assert len(np.unique(speed_groups([0.1, 0.102, 0.104, 0.3]))) == 3


def test_v085_gui_response_and_hysteresis(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtWidgets
    import pyqtgraph as pg
    from cdc_analyzer.gui_release_v085 import _build_release_gui_classes_v085
    from test_gui_v083 import _fake_response_result
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = _build_release_gui_classes_v085()()
    window.resize(1280, 800)
    pages = window.dynamic_pages
    pages.response_result = _fake_response_result()
    pages._rebuild_response_event_combo()
    window.tabs.setCurrentWidget(pages.response_page)
    pages.refresh_response_plot()
    window.show()
    for _ in range(3):
        app.processEvents()
    for manager in pages.response_annotations:
        manager.update()
        for item, x, y, level in manager.labels:
            assert not item.textItem.font().bold()
            assert item.textItem.font().pointSizeF() == manager.plot.getAxis("left").label.font().pointSizeF()
            assert item.fill.style().value == 0
        rects = manager.text_rects
        for i, rect in enumerate(rects):
            assert all(not rect.intersects(other) for other in rects[i + 1:])
        dots = [item for item in manager.plot.items if isinstance(item, pg.ScatterPlotItem)]
        assert len(dots) == 1
        for point in dots[0].points():
            signal = manager.plot.listDataItems()[0]
            assert point.pos().y() == pytest.approx(np.interp(point.pos().x(), signal.xData, signal.yData))
    pages.hysteresis_result = analyze_hysteresis_v085(multi_speed_data(), HysteresisConfig(standard=HysteresisStandard.BMW))
    pages._rebuild_hysteresis_views()
    assert pages.hysteresis_view_combo.count() == 1 + 4 + 3
    plot = pages.hysteresis_plot_area.getItem(0, 0)
    assert plot.getAxis("left").label.toPlainText().strip() == "压缩<--阻尼力(N)-->复原"
    ys = np.concatenate([p.yData for p in plot.listDataItems()])
    assert ys.min() < 0 < ys.max()
    for i in range(pages.hysteresis_view_combo.count()):
        pages.hysteresis_view_combo.setCurrentIndex(i)
        assert pages.hysteresis_plot_area.getItem(0, 0).listDataItems()
    from cdc_analyzer.dynamic_export import export_hysteresis_xlsx
    from openpyxl import load_workbook
    workbook_path = export_hysteresis_xlsx(pages.hysteresis_result, tmp_path / "grouped.xlsx")
    previous = pages.hysteresis_view_combo.currentIndex()
    pages._append_hysteresis_plot(workbook_path)
    assert pages.hysteresis_view_combo.currentIndex() == previous
    book = load_workbook(workbook_path)
    assert len(book["Hysteresis Plot"]._images) == 8
    book.close()
    window.close()
    app.processEvents()


def test_current_packaged_gui_is_v085():
    root = Path(__file__).resolve().parents[1]
    assert "gui_release_v085" in (root / "launcher.py").read_text()
    assert "gui_release_v085:main" in (root / "pyproject.toml").read_text()


@pytest.mark.parametrize("scale", ["1", "1.5"])
def test_display_scale_keeps_controls_and_annotations_readable(scale):
    import subprocess
    import sys
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_SCALE_FACTOR=scale,
               PYTHONPATH=str(root / "src") + os.pathsep + str(root / "tests"))
    completed = subprocess.run([sys.executable, str(root / "tests" / "probe_display_v085.py")],
                               env=env, capture_output=True, text=True, timeout=120)
    assert completed.returncode == 0, completed.stdout + completed.stderr
