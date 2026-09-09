from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from cdc_analyzer import runtime_dynamic_gui, runtime_gui_release


def test_canonical_runtime_has_no_versioned_gui_imports():
    dynamic_source = inspect.getsource(runtime_dynamic_gui)
    release_source = inspect.getsource(runtime_gui_release)
    assert "from .dynamic_gui_v" not in dynamic_source
    assert "from .gui_release_v" not in release_source
    assert "from .dynamic_gui_v" not in release_source


def test_canonical_controller_mro_is_self_contained():
    modules = {cls.__module__ for cls in runtime_dynamic_gui.DynamicPagesController.__mro__}
    assert "cdc_analyzer.runtime_dynamic_gui" in modules
    assert not any(module.startswith("cdc_analyzer.dynamic_gui_v") for module in modules)


def test_production_entrypoints_use_canonical_runtime():
    root = Path(__file__).resolve().parents[1]
    launcher = (root / "launcher.py").read_text(encoding="utf-8")
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "cdc_analyzer.runtime_gui_release" in launcher
    assert "cdc_analyzer.runtime_gui_release:main" in pyproject
    assert "gui_release_v084" not in launcher


def test_canonical_gui_builds_when_qt_available(monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    _QtCore, QtWidgets, _pg = runtime_gui_release._qt_imports()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    MainWindow = runtime_gui_release._build_release_gui_classes()
    window = MainWindow()
    try:
        assert window.dynamic_pages.__class__.__module__ == "cdc_analyzer.runtime_dynamic_gui"
        assert hasattr(window.dynamic_pages, "_add_curve_intersection_marker")
        assert hasattr(window.dynamic_pages, "response_target_speeds")
        assert hasattr(window, "file_menu")
        assert hasattr(window, "export_menu")
    finally:
        window.close()
        app.processEvents()
