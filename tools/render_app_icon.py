from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtGui, QtSvg

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "src" / "cdc_analyzer" / "assets"
SVG_PATH = ASSET_DIR / "damper_test_data_analyzer.svg"
PNG_PATH = ASSET_DIR / "damper_test_data_analyzer.png"


def main() -> int:
    renderer = QtSvg.QSvgRenderer(str(SVG_PATH))
    if not renderer.isValid():
        raise RuntimeError(f"Invalid SVG icon: {SVG_PATH}")

    size = 512
    image = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QtCore.QRectF(0, 0, size, size))
    painter.end()

    if not image.save(str(PNG_PATH), "PNG"):
        raise RuntimeError(f"Failed to save PNG icon: {PNG_PATH}")
    print(f"Rendered app icon: {PNG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
