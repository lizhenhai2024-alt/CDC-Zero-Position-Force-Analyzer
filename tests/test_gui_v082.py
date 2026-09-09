from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")


def test_v082_exposes_add_and_subtract_gas_force_operations():
    from PySide6 import QtWidgets
    from cdc_analyzer.gui_release_v082 import _build_release_gui_classes_v082

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    MainWindow = _build_release_gui_classes_v082()
    window = MainWindow()

    assert window.gas_operation.currentData() == "subtract"
    assert window.gas_operation.itemText(window.gas_operation.findData("subtract")) == "减去气体反弹力"
    assert window.gas_operation.itemText(window.gas_operation.findData("add")) == "加上气体反弹力"
    assert not window.gas_operation.isEnabled()

    window.gas_mode.setCurrentIndex(window.gas_mode.findData("direct"))
    window.gas_operation.setCurrentIndex(window.gas_operation.findData("add"))
    window.gas_force.setValue(200.0)
    config = window._config()
    assert window.gas_operation.isEnabled()
    assert config.gas_operation == "add"
    assert config.gas_force_n == pytest.approx(200.0)

    window.language_combo.setCurrentIndex(window.language_combo.findData("en_US"))
    app.processEvents()
    assert window.gas_operation.itemText(window.gas_operation.findData("subtract")) == "Subtract gas force"
    assert window.gas_operation.itemText(window.gas_operation.findData("add")) == "Add gas force"

    window.close()
    app.processEvents()


def test_v082_is_the_packaged_gui_entry_point():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    assert "gui_release_v082" in (root / "launcher.py").read_text(encoding="utf-8")
    assert 'cdc_analyzer.gui_release_v082:main' in (root / "pyproject.toml").read_text(encoding="utf-8")
