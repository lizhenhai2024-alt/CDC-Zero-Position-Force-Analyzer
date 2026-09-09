from __future__ import annotations

from math import pi
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from cdc_analyzer.analysis import AnalyzerConfig, CDCAnalyzer, EvaluationProfile
from cdc_analyzer.parser import DataSet
from cdc_analyzer.plotting import PlotSelection, available_plot_channels, evaluation_overlay, filter_processed_data


def synthetic_dataset(cycles: int = 2, current: float = 0.8) -> DataSet:
    n = cycles * 400 + 1
    theta = np.linspace(0, cycles * 2 * pi, n)
    t = theta / (2 * pi) * 4.0
    x = 50.0 * np.cos(theta)
    direction = np.sign(-np.sin(theta))
    force = np.where(direction >= 0, 1000.0 + 2.0 * x, -600.0 + x)
    df = pd.DataFrame({
        "Running Time": t,
        "Axial Displacement": x,
        "Axial Load": force,
        "CDC 1 Current FB_1": current + 0.0002 * np.sin(theta),
        "Block ID": 1,
        "Source Row": np.arange(1, n + 1),
    })
    return DataSet(df, Path("synthetic.dat"), "synthetic")


def test_plot_filtering_and_channel_order():
    result = CDCAnalyzer(AnalyzerConfig(profile=EvaluationProfile.AUDI)).analyze(synthetic_dataset(current=0.84))
    channels = available_plot_channels(result.processed)
    assert channels[:4] == ["Running Time", "Axial Displacement", "Axial Load", "CDC 1 Current FB_1"]
    run_id = int(result.runs.iloc[0]["Run ID"])
    filtered = filter_processed_data(result.processed, PlotSelection(current_label=0.8, run_id=run_id, cycle_id=2))
    assert not filtered.empty
    assert filtered["Run ID"].nunique() == 1
    assert filtered["Cycle ID"].dropna().astype(int).eq(2).all()


def test_audi_overlay_matches_selected_last_cycle_result():
    result = CDCAnalyzer(AnalyzerConfig(profile=EvaluationProfile.AUDI)).analyze(synthetic_dataset())
    run_id = int(result.runs.iloc[0]["Run ID"])
    overlay = evaluation_overlay(result, PlotSelection(run_id=run_id, cycle_id=2), "Axial Load")
    assert overlay is not None
    assert overlay.window_low_mm == pytest.approx(-5.0, abs=0.2)
    assert overlay.window_high_mm == pytest.approx(5.0, abs=0.2)
    assert overlay.rebound_force_n == pytest.approx(result.runs.iloc[0]["Rebound N"], abs=1e-9)
    assert overlay.compression_force_n == pytest.approx(result.runs.iloc[0]["Compression N"], abs=1e-9)


def test_gui_module_import_is_lazy_without_optional_dependencies():
    import cdc_analyzer.gui as gui
    assert callable(gui.main)
