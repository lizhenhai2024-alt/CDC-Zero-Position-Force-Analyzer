"""Separate-process DPI probe: QT_SCALE_FACTOR must be set before QApplication."""
import json
import os
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from cdc_analyzer.dynamic_analysis import HysteresisConfig, HysteresisStandard
from cdc_analyzer.gui_release_v085 import _build_release_gui_classes_v085
from cdc_analyzer.hysteresis_v085 import analyze_hysteresis_v085
from test_gui_v083 import _fake_response_result
from test_v085 import multi_speed_data

app = QtWidgets.QApplication([])
# The offscreen platform has no Windows font database. Load real system fonts
# for representative glyph metrics without changing the desktop display scale.
for name in ("segoeui.ttf", "msyh.ttc"):
    path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name
    if path.exists():
        QtGui.QFontDatabase.addApplicationFont(str(path))
font = QtGui.QFont("Segoe UI", 9)
font.setFamilies(["Segoe UI", "Microsoft YaHei"])
app.setFont(font)
window = _build_release_gui_classes_v085()()
scale = float(os.environ.get("QT_SCALE_FACTOR", 1))
window.resize(round(1920 / scale) - 40, round(1080 / scale) - 80)
pages = window.dynamic_pages
pages.response_result = _fake_response_result()
pages._rebuild_response_event_combo()
pages.refresh_response_plot()
window.tabs.setCurrentWidget(pages.response_page)
window.show()
for _ in range(5):
    app.processEvents()
assert window.width() <= round(1920 / scale)
for index in range(pages.response_flow.count()):
    item = pages.response_flow.itemAt(index)
    assert item.geometry().right() <= pages.response_flow.geometry().right() + 1
for trigger in (1.100, 1.140):
    pages.response_result.events.loc[0, "t0 s"] = trigger
    pages.response_result.events.loc[0, "Dead Time t1 ms"] = 0.8
    pages.response_result.events.loc[0, "Switch Time t63 ms"] = 2.0
    pages.response_result.events.loc[0, "Switch Time t90 ms"] = 3.0
    pages.refresh_response_plot()
    app.processEvents()
    for annotations in pages.response_annotations:
        annotations.update()
        rects = annotations.text_rects
        for i, rect in enumerate(rects):
            assert annotations.plot.vb.sceneBoundingRect().contains(rect)
            assert not any(rect.intersects(other) for other in rects[i + 1:]), str(annotations.plot.vb.sceneBoundingRect()) + repr([(r.x(),r.y(),r.width(),r.height()) for r in rects])
        for (item, x, y, level), rect in zip(annotations.labels, rects):
            if not level:
                point = annotations.plot.vb.mapViewToScene(QtCore.QPointF(x, y))
                assert abs(rect.center().x() - point.x()) < 1
out = os.environ.get("CDC_DISPLAY_OUTPUT")
if out:
    folder = Path(out)
    folder.mkdir(parents=True, exist_ok=True)
    window.grab().save(str(folder / f"response_{scale:g}.png"))
pages.hysteresis_result = analyze_hysteresis_v085(multi_speed_data(), HysteresisConfig(standard=HysteresisStandard.BMW))
pages._rebuild_hysteresis_views()
window.tabs.setCurrentWidget(pages.hysteresis_page)
for _ in range(5):
    app.processEvents()
if out:
    window.grab().save(str(folder / f"hysteresis_{scale:g}.png"))
print(json.dumps({"scale": scale, "device_pixel_ratio": window.devicePixelRatioF(),
                  "window": [window.width(), window.height()],
                  "annotation_font_pt": pages._font().pointSizeF(),
                  "hysteresis_views": pages.hysteresis_view_combo.count()}))
window.close()
