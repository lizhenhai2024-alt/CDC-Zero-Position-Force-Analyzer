"""Separate measured speed conditions before pairing hysteresis sweeps."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .dynamic_analysis import HysteresisAnalysisResult, HysteresisConfig, analyze_hysteresis
from .parser import DataSet


def speed_groups(values, relative_tolerance=0.03):
    """Cluster against a fixed first value, avoiding chained speed-bin drift."""
    values = np.asarray(values, dtype=float)
    if not np.all(np.isfinite(values) & (values > 0)):
        raise ValueError("迟滞速度必须为有限正数 / Hysteresis speeds must be finite and positive")
    labels = np.empty(len(values), dtype=float)
    remaining = np.argsort(values).tolist()
    while remaining:
        reference = values[remaining[0]]
        members = [i for i in remaining if values[i] <= reference * (1 + relative_tolerance)]
        labels[members] = float(np.mean(values[members]))
        selected = set(members)
        remaining = [i for i in remaining if i not in selected]
    return labels


def analyze_hysteresis_v085(dataset, config=None, *, speed_tolerance=0.03):
    config = config or HysteresisConfig()
    if not np.isfinite(speed_tolerance) or not 0 <= speed_tolerance < 1:
        raise ValueError("Speed grouping tolerance must be in [0, 1)")
    initial = analyze_hysteresis(dataset, config)
    speed_column = "Speed m/s" if "Speed m/s" in initial.runs else "Mean Speed m/s"
    block_speeds = initial.runs.groupby("Block ID", sort=False)[speed_column].mean()
    valid = block_speeds[np.isfinite(block_speeds) & (block_speeds > 0)]
    if len(valid) != len(block_speeds):
        raise ValueError("部分迟滞工况无法确定速度，请检查完整循环 / Cannot determine speed for every block")
    grouped = pd.Series(speed_groups(valid.to_numpy(), speed_tolerance), index=valid.index)
    results = []
    for speed in sorted(grouped.unique()):
        ids = grouped.index[grouped == speed]
        raw = dataset.data
        selected = raw[raw["Block ID"].isin(ids)].copy() if "Block ID" in raw else raw.copy()
        part = analyze_hysteresis(DataSet(selected, dataset.source_path, dataset.source_format, dataset.metadata), config)
        part.runs["Speed Group m/s"] = speed
        part.summary["Speed Group m/s"] = speed
        if "Current Label A" not in part.runs:
            part.runs["Current Label A"] = part.runs["Current A"].round(config.current_decimals)
        # Audi retains acquisition order; connecting this order shows the
        # actual excursions instead of inventing an ascending-current sweep.
        results.append(part)
    settings = dict(initial.settings)
    settings.update({"Speed Grouping Tolerance %": speed_tolerance * 100,
                     "Speed Groups m/s": ", ".join(f"{v:.6g}" for v in sorted(grouped.unique())),
                     "Speed Pairing": "Separate measured speed groups; never average across speeds"})
    return HysteresisAnalysisResult(
        pd.concat([r.processed for r in results], ignore_index=True),
        pd.concat([r.runs for r in results], ignore_index=True),
        pd.concat([r.summary for r in results], ignore_index=True),
        settings, dataset.source_path,
    )
