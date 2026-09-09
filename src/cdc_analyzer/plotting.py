from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from .analysis import CORRECTED, CURRENT, DISP, GAS_CORRECTION, LOAD, TIME, AnalysisResult, EvaluationProfile

PLOT_UNITS: dict[str, str] = {
    TIME: "s",
    DISP: "mm",
    LOAD: "N",
    "Analysis Axial Load": "N",
    CORRECTED: "N",
    CURRENT: "A",
    "Gas Force": "N",
    GAS_CORRECTION: "N",
    "Current Actual": "A",
    "Current Label": "A",
}

DEFAULT_PLOT_CHANNELS = [TIME, DISP, LOAD, CURRENT, CORRECTED, "Gas Force", GAS_CORRECTION]


@dataclass(frozen=True, slots=True)
class PlotSelection:
    current_label: float | None = None
    run_id: int | None = None
    cycle_id: int | None = None


@dataclass(frozen=True, slots=True)
class EvaluationOverlay:
    window_low_mm: float
    window_high_mm: float
    rebound_x_mm: float | None
    rebound_force_n: float | None
    compression_x_mm: float | None
    compression_force_n: float | None


def available_plot_channels(df: pd.DataFrame) -> list[str]:
    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    ordered = [c for c in DEFAULT_PLOT_CHANNELS if c in numeric]
    ordered.extend(c for c in numeric if c not in ordered)
    return ordered


def filter_processed_data(df: pd.DataFrame, selection: PlotSelection) -> pd.DataFrame:
    out = df
    if selection.current_label is not None and "Current Label" in out.columns:
        out = out[np.isclose(out["Current Label"].astype(float), float(selection.current_label), atol=1e-9)]
    if selection.run_id is not None and "Run ID" in out.columns:
        out = out[out["Run ID"].astype(float) == float(selection.run_id)]
    if selection.cycle_id is not None and "Cycle ID" in out.columns:
        out = out[out["Cycle ID"].astype(float) == float(selection.cycle_id)]
    return out.copy()


def _selected_cycle_row(result: AnalysisResult, selection: PlotSelection) -> pd.Series | None:
    if result.cycles.empty or selection.run_id is None:
        return None
    rows = result.cycles[result.cycles["Run ID"].astype(int) == int(selection.run_id)]
    if selection.cycle_id is not None:
        rows = rows[rows["Cycle ID"].astype(int) == int(selection.cycle_id)]
    return None if rows.empty else rows.iloc[-1]


def evaluation_overlay(result: AnalysisResult, selection: PlotSelection, force_column: str) -> EvaluationOverlay | None:
    row = _selected_cycle_row(result, selection)
    if row is None:
        return None
    low, high = float(row["Window Low mm"]), float(row["Window High mm"])
    cycle_id = int(row["Cycle ID"])
    data = filter_processed_data(
        result.processed,
        PlotSelection(current_label=selection.current_label, run_id=selection.run_id, cycle_id=cycle_id),
    )
    if data.empty or force_column not in data.columns:
        return EvaluationOverlay(low, high, None, None, None, None)
    window = data[data[DISP].between(low, high)]
    rb = window[window["Motion Direction"].eq("Rebound")]
    cp = window[window["Motion Direction"].eq("Compression")]

    def point(frame: pd.DataFrame, kind: str) -> tuple[float | None, float | None]:
        if frame.empty:
            return None, None
        if result.settings.get("profile") == EvaluationProfile.AUDI.value:
            idx = frame[force_column].idxmax() if kind == "rebound" else frame[force_column].idxmin()
            return float(frame.loc[idx, DISP]), float(frame.loc[idx, force_column])
        force = float(row["Rebound N"] if kind == "rebound" else row["Compression N"])
        x = float(row["Center Position mm"])
        if result.settings.get("profile") == EvaluationProfile.ZERO_CROSSING.value:
            x = float(result.settings.get("zero_target_mm", x))
        return x, force

    rx, rf = point(rb, "rebound")
    cx, cf = point(cp, "compression")
    return EvaluationOverlay(low, high, rx, rf, cx, cf)


def unit_for_channel(channel: str) -> str:
    return PLOT_UNITS.get(channel, "")


def same_units(channels: Iterable[str]) -> bool:
    return len({unit_for_channel(c) for c in channels}) <= 1
