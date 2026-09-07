from __future__ import annotations

import numpy as np
import pandas as pd

from cdc_analyzer.sweep import build_sweep_comparison


def test_sweep_comparison_pairs_up_and_down_and_uses_down_minus_up():
    runs = pd.DataFrame(
        [
            {"Run ID": 1, "Current Label A": 0.7, "Sweep Direction": "Up", "Rebound N": 360.0, "Compression N": -650.0},
            {"Run ID": 2, "Current Label A": 0.9, "Sweep Direction": "Up", "Rebound N": 840.0, "Compression N": -770.0},
            {"Run ID": 3, "Current Label A": 0.9, "Sweep Direction": "Down", "Rebound N": 880.0, "Compression N": -781.0},
            {"Run ID": 4, "Current Label A": 0.7, "Sweep Direction": "Down", "Rebound N": 426.0, "Compression N": -664.0},
        ]
    )
    table = build_sweep_comparison(runs)
    row = table.loc[table["Current Label A"] == 0.7].iloc[0]
    assert row["Coverage"] == "Up + Down"
    assert row["Delta Rebound N"] == 66.0
    assert row["Delta Compression N"] == -14.0


def test_sweep_comparison_keeps_turning_point_as_single_sweep_without_pass_fail():
    runs = pd.DataFrame(
        [{"Run ID": 1, "Current Label A": 1.7, "Sweep Direction": "Up", "Rebound N": 1470.0, "Compression N": -859.0}]
    )
    table = build_sweep_comparison(runs)
    row = table.iloc[0]
    assert row["Coverage"] == "Up only"
    assert np.isnan(row["Down Rebound N"])
    assert np.isnan(row["Delta Rebound N"])
