from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import pi
from typing import Literal

import numpy as np
import pandas as pd

from .parser import DataSet

TIME = "Running Time"
DISP = "Axial Displacement"
LOAD = "Axial Load"
CURRENT = "CDC 1 Current FB_1"
CORRECTED = "Corrected Axial Load"
GAS_CORRECTION = "Gas Force Correction"


class EvaluationProfile(str, Enum):
    AUDI = "audi"
    WINDOW_MEAN = "window_mean"
    ZERO_CROSSING = "zero_crossing"


@dataclass(slots=True)
class AnalyzerConfig:
    current_decimals: int = 1
    current_stability_std_a: float = 0.03
    min_run_duration_s: float = 0.5
    reverse_displacement_direction: bool = False
    reverse_load_sign: bool = False
    profile: EvaluationProfile = EvaluationProfile.AUDI
    force_channel: Literal["raw", "corrected"] = "raw"
    window_percent: float = 2.0
    window_basis: Literal["amplitude", "total_stroke"] = "amplitude"
    window_min_points_per_direction: int = 3
    zero_target_mm: float = 0.0
    gas_mode: Literal["off", "direct", "pressure"] = "off"
    gas_operation: Literal["subtract", "add"] = "subtract"
    gas_force_n: float = 0.0
    gas_gauge_pressure_mpa: float = 0.0
    piston_rod_diameter_mm: float = 0.0
    cycle_min_span_fraction: float = 0.80


@dataclass(slots=True)
class AnalysisResult:
    processed: pd.DataFrame
    cycles: pd.DataFrame
    runs: pd.DataFrame
    summary: pd.DataFrame
    settings: dict[str, object]


def gas_force_from_pressure(pressure_mpa: float, rod_diameter_mm: float) -> float:
    if pressure_mpa < 0 or rod_diameter_mm < 0:
        raise ValueError("Gas pressure and rod diameter must be non-negative")
    return pressure_mpa * pi * rod_diameter_mm**2 / 4.0


def _smooth(x: np.ndarray, n: int = 5) -> np.ndarray:
    if len(x) < n:
        return x.astype(float, copy=True)
    p = np.pad(x.astype(float), (n // 2, n // 2), mode="edge")
    return np.convolve(p, np.ones(n) / n, mode="valid")[: len(x)]


def _fill_sign(s: np.ndarray) -> np.ndarray:
    s = s.copy()
    for i in range(1, len(s)):
        if s[i] == 0:
            s[i] = s[i - 1]
    for i in range(len(s) - 2, -1, -1):
        if s[i] == 0:
            s[i] = s[i + 1]
    return s


def _crossings(x: np.ndarray, center: float) -> np.ndarray:
    z = x - center
    return np.array(
        [i for i in range(len(z) - 1) if not (z[i] == z[i + 1] == 0) and z[i] * z[i + 1] <= 0],
        dtype=int,
    )


def _dedupe(points: list[int], x: np.ndarray, min_distance: int, take_max: bool) -> list[int]:
    if not points:
        return []
    groups = [[points[0]]]
    for p in points[1:]:
        if p - groups[-1][-1] < min_distance:
            groups[-1].append(p)
        else:
            groups.append([p])
    chooser = max if take_max else min
    return [chooser(g, key=lambda i: x[i]) for g in groups]


def _extrema(x: np.ndarray) -> tuple[list[int], list[int]]:
    xs = _smooth(x)
    if len(xs) < 5:
        return [], []
    d = _fill_sign(np.sign(np.diff(xs)))
    center = (xs.max() + xs.min()) / 2
    stroke = xs.max() - xs.min()
    high, low = center + 0.30 * stroke, center - 0.30 * stroke
    maxima = [i for i in range(1, len(d)) if d[i - 1] > 0 > d[i] and xs[i] >= high]
    minima = [i for i in range(1, len(d)) if d[i - 1] < 0 < d[i] and xs[i] <= low]
    c = _crossings(xs, center)
    min_dist = int(max(2, 0.9 * np.median(np.diff(c)))) if len(c) >= 3 else max(2, len(xs) // 3)
    if xs[0] >= high:
        maxima.insert(0, 0)
    if xs[-1] >= high:
        maxima.append(len(xs) - 1)
    if xs[0] <= low:
        minima.insert(0, 0)
    if xs[-1] <= low:
        minima.append(len(xs) - 1)
    return (
        _dedupe(sorted(set(maxima)), xs, min_dist, True),
        _dedupe(sorted(set(minima)), xs, min_dist, False),
    )


def _cycles_between(x: np.ndarray, bounds: list[int], min_span_fraction: float) -> list[tuple[int, int]]:
    full_span = float(np.ptp(x))
    if full_span <= 0:
        return []
    return [
        (a, b)
        for a, b in zip(bounds[:-1], bounds[1:])
        if b - a >= 4 and float(np.ptp(x[a : b + 1])) >= min_span_fraction * full_span
    ]


def detect_complete_cycles(run: pd.DataFrame, config: AnalyzerConfig) -> list[tuple[int, int]]:
    x = run[DISP].to_numpy(float)
    if config.reverse_displacement_direction:
        x = -x
    maxima, minima = _extrema(x)
    a = _cycles_between(x, maxima, config.cycle_min_span_fraction)
    b = _cycles_between(x, minima, config.cycle_min_span_fraction)
    return a if len(a) >= len(b) else b


def _interpolate(seg: pd.DataFrame, target: float, direction: str, force_col: str) -> float | None:
    x, f, t = (seg[c].to_numpy(float) for c in (DISP, force_col, TIME))
    v = np.gradient(x, t)
    wanted = 1 if direction == "Rebound" else -1
    values: list[float] = []
    for i in range(len(x) - 1):
        if v[i] * wanted <= 0 and v[i + 1] * wanted <= 0:
            continue
        if x[i] == target:
            values.append(float(f[i]))
        elif (x[i] - target) * (x[i + 1] - target) <= 0 and x[i] != x[i + 1]:
            q = (target - x[i]) / (x[i + 1] - x[i])
            values.append(float(f[i] + q * (f[i + 1] - f[i])))
    return float(np.median(values)) if values else None


class CDCAnalyzer:
    def __init__(self, config: AnalyzerConfig | None = None):
        self.config = config or AnalyzerConfig()

    def _gas_force(self) -> float:
        c = self.config
        if c.gas_mode == "off":
            return 0.0
        if c.gas_mode == "direct":
            if c.gas_force_n < 0:
                raise ValueError("Gas force cannot be negative")
            return float(c.gas_force_n)
        if c.gas_mode == "pressure":
            return gas_force_from_pressure(c.gas_gauge_pressure_mpa, c.piston_rod_diameter_mm)
        raise ValueError(f"Unsupported gas mode: {c.gas_mode}")

    def _gas_correction(self) -> float:
        operation = self.config.gas_operation
        if operation not in {"subtract", "add"}:
            raise ValueError(f"Unsupported gas operation: {operation}")
        force = self._gas_force()
        return force if operation == "add" else -force

    def _prepare(self, dataset: DataSet) -> pd.DataFrame:
        df = dataset.data.copy()
        df["Analysis Axial Load"] = (-1 if self.config.reverse_load_sign else 1) * df[LOAD].astype(float)
        gas_force = self._gas_force()
        gas_correction = self._gas_correction()
        df["Gas Force"] = gas_force
        df[GAS_CORRECTION] = gas_correction
        df[CORRECTED] = df["Analysis Axial Load"] + df[GAS_CORRECTION]
        motion = pd.Series(index=df.index, dtype="object")
        for _, block in df.groupby("Block ID", sort=False):
            x = block[DISP].to_numpy(float) * (-1 if self.config.reverse_displacement_direction else 1)
            t = block[TIME].to_numpy(float)
            v = np.gradient(x, t) if len(block) > 1 else np.zeros(len(block))
            motion.loc[block.index] = np.where(v > 0, "Rebound", np.where(v < 0, "Compression", "Unknown"))
        df["Motion Direction"] = motion
        return df

    def _assign_runs(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["Current Label"] = out[CURRENT].round(self.config.current_decimals)
        key = out["Block ID"].astype(str) + "|" + out["Current Label"].astype(str)
        out["Run ID"] = key.ne(key.shift()).cumsum().astype(int)
        out["Current Actual"] = out.groupby("Run ID")[CURRENT].transform("median")
        labels = out.groupby("Run ID", sort=False)["Current Label"].first().tolist()
        sweeps: dict[int, str] = {}
        for i, label in enumerate(labels):
            prev = label - labels[i - 1] if i else 0.0
            nxt = labels[i + 1] - label if i + 1 < len(labels) else 0.0
            d = prev if prev else nxt
            sweeps[i + 1] = "Up" if d > 0 else "Down" if d < 0 else "Hold"
        out["Sweep Direction"] = out["Run ID"].map(sweeps)
        return out

    def _evaluate_cycle(self, cycle: pd.DataFrame, cycle_id: int, run_id: int, force_col: str) -> dict[str, object]:
        c = self.config
        x = cycle[DISP].to_numpy(float)
        center, stroke = (float(x.max() + x.min()) / 2.0, float(np.ptp(x)))
        row: dict[str, object] = {
            "Run ID": run_id,
            "Cycle ID": cycle_id,
            "Complete": True,
            "Center Position mm": center,
            "Total Stroke mm": stroke,
            "Start Time s": float(cycle[TIME].iloc[0]),
            "End Time s": float(cycle[TIME].iloc[-1]),
        }
        motion = cycle["Motion Direction"]
        if c.profile == EvaluationProfile.AUDI:
            half = 0.05 * stroke
            low, high = center - half, center + half
            mask = cycle[DISP].between(low, high)
            rb = cycle.loc[mask & motion.eq("Rebound"), force_col]
            cp = cycle.loc[mask & motion.eq("Compression"), force_col]
            basis = "10% total stroke (Audi)"
            rebound = float(rb.max()) if len(rb) else np.nan
            compression = float(cp.min()) if len(cp) else np.nan
        elif c.profile == EvaluationProfile.WINDOW_MEAN:
            if c.window_percent <= 0:
                raise ValueError("Window percent must be > 0")
            half = c.window_percent / 100.0 * stroke / 2.0
            low, high = center - half, center + half
            mask = cycle[DISP].between(low, high)
            rb = cycle.loc[mask & motion.eq("Rebound"), force_col]
            cp = cycle.loc[mask & motion.eq("Compression"), force_col]
            basis = f"{c.window_percent:g}% {c.window_basis}"
            rebound = float(rb.mean()) if len(rb) else np.nan
            compression = float(cp.mean()) if len(cp) else np.nan
        elif c.profile == EvaluationProfile.ZERO_CROSSING:
            low = high = c.zero_target_mm
            basis = "zero crossing interpolation"
            r = _interpolate(cycle, c.zero_target_mm, "Rebound", force_col)
            p = _interpolate(cycle, c.zero_target_mm, "Compression", force_col)
            rb = [0, 1] if r is not None else []
            cp = [0, 1] if p is not None else []
            rebound = float(r) if r is not None else np.nan
            compression = float(p) if p is not None else np.nan
        else:
            raise ValueError(f"Unsupported profile: {c.profile}")
        row.update({
            "Window Low mm": low,
            "Window High mm": high,
            "Window Basis": basis,
            "Rebound Point Count": len(rb),
            "Compression Point Count": len(cp),
            "Rebound N": rebound,
            "Compression N": compression,
        })
        issues: list[str] = []
        if np.isnan(rebound) or np.isnan(compression):
            issues.append("missing evaluation data")
        if c.profile == EvaluationProfile.WINDOW_MEAN:
            if len(rb) < c.window_min_points_per_direction:
                issues.append("insufficient rebound window points")
            if len(cp) < c.window_min_points_per_direction:
                issues.append("insufficient compression window points")
        if not np.isnan(rebound) and rebound <= 0:
            issues.append("unexpected rebound force sign")
        if not np.isnan(compression) and compression >= 0:
            issues.append("unexpected compression force sign")
        row["Status"] = "OK" if not issues else "Warning"
        row["Issues"] = "; ".join(issues)
        return row

    def analyze(self, dataset: DataSet) -> AnalysisResult:
        df = self._assign_runs(self._prepare(dataset))
        force_col = "Analysis Axial Load" if self.config.force_channel == "raw" else CORRECTED
        cycle_rows, run_rows = [], []
        global_cycle = 0
        for run_id, run in df.groupby("Run ID", sort=False):
            run = run.copy()
            bounds = detect_complete_cycles(run, self.config)
            evaluated = []
            for cycle_id, (a, b) in enumerate(bounds, 1):
                global_cycle += 1
                cycle = run.iloc[a : b + 1]
                row = self._evaluate_cycle(cycle, cycle_id, int(run_id), force_col)
                row.update({
                    "Global Cycle ID": global_cycle,
                    "Current Label A": float(run["Current Label"].iloc[0]),
                    "Current Actual A": float(run[CURRENT].median()),
                    "Sweep Direction": str(run["Sweep Direction"].iloc[0]),
                    "Force Channel": force_col,
                })
                cycle_rows.append(row)
                evaluated.append(row)
                df.loc[cycle.index, "Cycle ID"] = cycle_id
            current_std = float(run[CURRENT].std(ddof=0)) if len(run) > 1 else 0.0
            duration = float(run[TIME].iloc[-1] - run[TIME].iloc[0]) if len(run) > 1 else 0.0
            selected = evaluated[-1] if evaluated else None
            issues = []
            if duration < self.config.min_run_duration_s:
                issues.append("run too short")
            if current_std > self.config.current_stability_std_a:
                issues.append("current unstable")
            if selected is None:
                issues.append("no complete cycle")
            elif selected["Status"] != "OK":
                issues.append(str(selected["Issues"]))
            run_rows.append({
                "Run ID": int(run_id),
                "Current Label A": float(run["Current Label"].iloc[0]),
                "Current Actual A": float(run[CURRENT].median()),
                "Current Std A": current_std,
                "Sweep Direction": str(run["Sweep Direction"].iloc[0]),
                "Duration s": duration,
                "Complete Cycle Count": len(bounds),
                "Selected Cycle ID": selected["Cycle ID"] if selected else np.nan,
                "Rebound N": selected["Rebound N"] if selected else np.nan,
                "Compression N": selected["Compression N"] if selected else np.nan,
                "Status": "OK" if not issues else "Warning",
                "Issues": "; ".join(dict.fromkeys(issues)),
            })
        cycles, runs = pd.DataFrame(cycle_rows), pd.DataFrame(run_rows)
        valid = runs.dropna(subset=["Rebound N", "Compression N"])
        if valid.empty:
            summary = pd.DataFrame(columns=["Current Label A", "Rebound N", "Compression N", "Run Count", "Status"])
        else:
            summary = valid.groupby("Current Label A", as_index=False).agg(
                **{
                    "Rebound N": ("Rebound N", "mean"),
                    "Compression N": ("Compression N", "mean"),
                    "Run Count": ("Run ID", "count"),
                    "Rebound SD N": ("Rebound N", lambda s: float(s.std(ddof=0))),
                    "Compression SD N": ("Compression N", lambda s: float(s.std(ddof=0))),
                }
            ).sort_values("Current Label A").reset_index(drop=True)
            status = valid.groupby("Current Label A")["Status"].apply(lambda s: "OK" if (s == "OK").all() else "Warning")
            summary["Status"] = summary["Current Label A"].map(status)
            summary["Evaluation Profile"] = self.config.profile.value
            summary["Force Channel"] = force_col
        settings = {
            "source_file": dataset.source_path.name,
            "source_format": dataset.source_format,
            "profile": self.config.profile.value,
            "force_channel": force_col,
            "current_decimals": self.config.current_decimals,
            "gas_mode": self.config.gas_mode,
            "gas_operation": self.config.gas_operation,
            "gas_force_n": self._gas_force(),
            "gas_correction_n": self._gas_correction(),
            "window_percent": self.config.window_percent,
            "window_basis": self.config.window_basis,
            "zero_target_mm": self.config.zero_target_mm,
        }
        return AnalysisResult(df, cycles, runs, summary, settings)
