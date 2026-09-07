from __future__ import annotations

from math import pi
from pathlib import Path

import numpy as np
import pandas as pd

from cdc_analyzer.analysis import AnalyzerConfig, CDCAnalyzer, EvaluationProfile, gas_force_from_pressure
from cdc_analyzer.parser import DataSet, load_test_data


def synthetic_dataset(cycles: int = 2, current: float = 0.8) -> DataSet:
    n = cycles * 400 + 1
    theta = np.linspace(0, cycles * 2 * pi, n)
    t = theta / (2 * pi) * 4.0
    x = 50.0 * np.cos(theta)
    v_sign = np.sign(-np.sin(theta))
    force = np.where(v_sign >= 0, 1000.0 + 2.0 * x, -600.0 + 1.0 * x)
    df = pd.DataFrame(
        {
            "Running Time": t,
            "Axial Displacement": x,
            "Axial Load": force,
            "CDC 1 Current FB_1": current + 0.0002 * np.sin(theta),
            "Block ID": 1,
            "Source Row": np.arange(1, n + 1),
        }
    )
    return DataSet(df, Path("synthetic.dat"), "synthetic")


def pytest_approx(value: float, tol: float):
    import pytest
    return pytest.approx(value, abs=tol)


def test_gas_pressure_formula():
    assert gas_force_from_pressure(0.8, 18.0) == pytest_approx(0.8 * pi * 18.0**2 / 4.0, 1e-9)


def test_audi_profile_uses_last_complete_cycle_and_directional_peak():
    result = CDCAnalyzer(AnalyzerConfig(profile=EvaluationProfile.AUDI)).analyze(synthetic_dataset(cycles=2))
    run = result.runs.iloc[0]
    assert int(run["Complete Cycle Count"]) == 2
    assert run["Rebound N"] == pytest_approx(1010.0, 1.0)
    assert run["Compression N"] == pytest_approx(-605.0, 1.0)


def test_window_mean_and_gas_correction():
    cfg = AnalyzerConfig(
        profile=EvaluationProfile.WINDOW_MEAN,
        window_percent=2.0,
        window_basis="amplitude",
        gas_mode="direct",
        gas_force_n=200.0,
        force_channel="corrected",
    )
    result = CDCAnalyzer(cfg).analyze(synthetic_dataset(cycles=1))
    run = result.runs.iloc[0]
    assert run["Rebound N"] == pytest_approx(800.0, 2.0)
    assert run["Compression N"] == pytest_approx(-800.0, 2.0)


def test_zero_crossing_interpolation():
    cfg = AnalyzerConfig(profile=EvaluationProfile.ZERO_CROSSING)
    result = CDCAnalyzer(cfg).analyze(synthetic_dataset(cycles=1))
    run = result.runs.iloc[0]
    assert run["Rebound N"] == pytest_approx(1000.0, 1.0)
    assert run["Compression N"] == pytest_approx(-600.0, 1.0)


def test_mts_parser_repeated_blocks(tmp_path: Path):
    content = """MTS793|MPT|ENU|1|2|.|/|:|1|0|0|A

Data Acquisition\t\tTime:\t4\ts
Running Time\tAxial Displacement\tAxial Load\tCDC 1 Current FB_1
s\tmm\tN\tA
0.0\t50\t-500\t0.3
0.1\t0\t-550\t0.3
0.2\t-50\t-400\t0.3

Data Acquisition\t\tTime:\t8\ts
Running Time\tAxial Displacement\tAxial Load\tCDC 1 Current FB_1
s\tmm\tN\tA
0.3\t-50\t300\t0.5
0.4\t0\t500\t0.5
0.5\t50\t600\t0.5
"""
    p = tmp_path / "sample.dat"
    p.write_text(content, encoding="utf-8")
    ds = load_test_data(p)
    assert len(ds.data) == 6
    assert ds.metadata["block_count"] == 2
    assert list(ds.data["Block ID"].unique()) == [1, 2]
