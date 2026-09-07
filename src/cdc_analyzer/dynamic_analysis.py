from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import ceil
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from .parser import DataSet, load_test_data

TIME = "Running Time"
DISP = "Axial Displacement"
LOAD = "Axial Load"
CURRENT = "CDC 1 Current FB_1"
VELOCITY = "Velocity m/s"


class ResponseStandard(str, Enum):
    AUDI = "audi"
    BMW = "bmw"


class HysteresisStandard(str, Enum):
    AUDI = "audi"
    BMW = "bmw"


@dataclass(slots=True)
class ResponseConfig:
    standard: ResponseStandard = ResponseStandard.AUDI
    trigger_fraction: float = 0.10
    end_average_fraction: float = 0.02
    plateau_fraction: float = 0.15
    min_current_step_a: float = 0.05
    event_derivative_fraction: float = 0.20
    min_event_separation_s: float = 0.003
    t90_limit_ms: float | None = None


@dataclass(slots=True)
class ResponseAnalysisResult:
    processed: pd.DataFrame
    events: pd.DataFrame
    settings: dict[str, object]
    source_path: Path


@dataclass(slots=True)
class HysteresisConfig:
    standard: HysteresisStandard = HysteresisStandard.BMW
    current_decimals: int = 1
    zero_target_mm: float = 0.0
    limit_percent: float | None = None
    audi_soft_current_a: float | None = None
    audi_kfm_current_a: float | None = None
    audi_hard_current_a: float | None = None
    audi_min_mean_cycles: int = 4
    audi_smoothing_fraction_per_side: float = 0.03


@dataclass(slots=True)
class HysteresisAnalysisResult:
    processed: pd.DataFrame
    runs: pd.DataFrame
    summary: pd.DataFrame
    settings: dict[str, object]
    source_path: Path


def _sample_rate_hz(frame: pd.DataFrame) -> float:
    t = frame[TIME].to_numpy(float)
    dt = np.diff(t)
    dt = dt[np.isfinite(dt) & (dt > 0)]
    return float(1.0 / np.median(dt)) if len(dt) else float("nan")


def _interpolate_time(t: np.ndarray, y: np.ndarray, target_t: float) -> float:
    return float(np.interp(target_t, t, y))


def _first_level_crossing(
    t: np.ndarray,
    y: np.ndarray,
    target: float,
    start_idx: int = 0,
    direction: int = 0,
) -> float | None:
    """Return the first linearly interpolated threshold crossing."""
    for i in range(max(0, start_idx), len(y) - 1):
        y0, y1 = float(y[i]), float(y[i + 1])
        if direction > 0 and max(y0, y1) < target:
            continue
        if direction < 0 and min(y0, y1) > target:
            continue
        if (y0 - target) * (y1 - target) <= 0 and y1 != y0:
            q = (target - y0) / (y1 - y0)
            return float(t[i] + q * (t[i + 1] - t[i]))
    return None


def _numeric_rows(path: Path, columns: int = 4) -> np.ndarray:
    rows: list[list[float]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("\t")
        if len(parts) < columns:
            continue
        try:
            values = [float(parts[i].strip()) for i in range(columns)]
        except ValueError:
            continue
        rows.append(values)
    if len(rows) < 8:
        raise ValueError("Headerless numeric DAT does not contain enough four-channel numeric rows")
    return np.asarray(rows, dtype=float)


def _infer_headerless_channels(matrix: np.ndarray) -> tuple[pd.DataFrame, dict[str, object]]:
    if matrix.ndim != 2 or matrix.shape[1] != 4:
        raise ValueError("Channel inference expects four numeric columns")

    time_candidates: list[tuple[float, float, int]] = []
    for col in range(4):
        d = np.diff(matrix[:, col])
        positive_ratio = float(np.mean(d > 0)) if len(d) else 0.0
        if positive_ratio >= 0.98:
            mean_d = float(np.mean(d))
            cv = float(np.std(d) / max(abs(mean_d), 1e-12))
            time_candidates.append((positive_ratio, -cv, col))
    if not time_candidates:
        raise ValueError("Could not infer a monotonically increasing time channel")
    time_col = max(time_candidates)[2]

    remaining = [col for col in range(4) if col != time_col]
    current_candidates: list[tuple[float, float, int]] = []
    for col in remaining:
        values = matrix[:, col]
        q99 = float(np.quantile(np.abs(values), 0.99))
        span = float(np.ptp(values))
        if q99 <= 10.0 and span >= 0.02:
            current_candidates.append((q99, span, col))
    if not current_candidates:
        raise ValueError("Could not infer a current feedback channel")
    current_col = min(current_candidates, key=lambda item: item[0])[2]

    remaining = [col for col in remaining if col != current_col]
    scales = sorted((float(np.quantile(np.abs(matrix[:, col]), 0.95)), col) for col in remaining)
    displacement_col = scales[0][1]
    load_col = scales[-1][1]

    frame = pd.DataFrame(
        {
            TIME: matrix[:, time_col],
            DISP: matrix[:, displacement_col],
            LOAD: matrix[:, load_col],
            CURRENT: matrix[:, current_col],
        }
    )
    frame["Block ID"] = 1
    frame["Source Row"] = range(1, len(frame) + 1)
    mapping = {
        "time_column_1based": time_col + 1,
        "load_column_1based": load_col + 1,
        "current_column_1based": current_col + 1,
        "displacement_column_1based": displacement_col + 1,
        "inference": "heuristic",
    }
    return frame, mapping


def load_dynamic_test_data(path: str | Path) -> DataSet:
    """Load ordinary MTS/tabular data or infer a headerless four-channel response DAT."""
    source = Path(path)
    try:
        return load_test_data(source)
    except ValueError:
        if source.suffix.lower() != ".dat":
            raise
    matrix = _numeric_rows(source, 4)
    frame, mapping = _infer_headerless_channels(matrix)
    return DataSet(
        data=frame,
        source_path=source,
        source_format="headerless_numeric_dat",
        metadata={"block_count": 1, "inferred_mapping": mapping},
    )


def _detect_current_events(frame: pd.DataFrame, config: ResponseConfig) -> list[int]:
    t = frame[TIME].to_numpy(float)
    current = frame[CURRENT].to_numpy(float)
    if len(current) < 8:
        return []

    padded = np.pad(current, (1, 1), mode="edge")
    smooth = np.convolve(padded, np.ones(3) / 3.0, mode="valid")
    slope = np.abs(np.gradient(smooth, t))
    peak = float(np.nanmax(slope))
    if not np.isfinite(peak) or peak <= 0:
        return []

    mask = slope >= config.event_derivative_fraction * peak
    groups: list[list[int]] = []
    active: list[int] = []
    for idx, state in enumerate(mask):
        if state:
            active.append(idx)
        elif active:
            groups.append(active)
            active = []
    if active:
        groups.append(active)

    candidates = [max(group, key=lambda index: slope[index]) for group in groups]
    events: list[int] = []
    for candidate in candidates:
        if not events or t[candidate] - t[events[-1]] >= config.min_event_separation_s:
            events.append(candidate)
        elif slope[candidate] > slope[events[-1]]:
            events[-1] = candidate
    return events


def analyze_response_time(dataset: DataSet, config: ResponseConfig | None = None) -> ResponseAnalysisResult:
    config = config or ResponseConfig()
    if not 0 < config.trigger_fraction < 1:
        raise ValueError("Trigger fraction must be between 0 and 1")
    if not 0 < config.end_average_fraction <= 0.5:
        raise ValueError("End-average fraction must be in (0, 0.5]")

    data = (
        dataset.data[[TIME, DISP, LOAD, CURRENT]]
        .dropna()
        .sort_values(TIME)
        .reset_index(drop=True)
        .copy()
    )
    if len(data) < 8:
        raise ValueError("Response-time analysis requires at least 8 valid samples")

    t = data[TIME].to_numpy(float)
    x = data[DISP].to_numpy(float)
    data[VELOCITY] = np.gradient(x, t) / 1000.0

    events = _detect_current_events(data, config)
    if not events:
        events = [int(np.argmax(np.abs(np.gradient(data[CURRENT].to_numpy(float), t))))]

    boundaries = [0]
    boundaries.extend((left + right) // 2 for left, right in zip(events[:-1], events[1:]))
    boundaries.append(len(data) - 1)

    rows: list[dict[str, object]] = []
    for event_no, event_index in enumerate(events, start=1):
        start = boundaries[event_no - 1]
        end = boundaries[event_no]
        segment = data.iloc[start : end + 1].reset_index(drop=True)
        if len(segment) < 10:
            continue

        ts = segment[TIME].to_numpy(float)
        xs = segment[DISP].to_numpy(float)
        fs = segment[LOAD].to_numpy(float)
        currents = segment[CURRENT].to_numpy(float)
        velocities = segment[VELOCITY].to_numpy(float)
        n = len(segment)
        plateau_n = max(3, int(round(config.plateau_fraction * n)))
        current_start = float(np.median(currents[:plateau_n]))
        current_end = float(np.median(currents[-plateau_n:]))
        delta_current = current_end - current_start
        if abs(delta_current) < config.min_current_step_a:
            continue

        trigger_current = current_start + config.trigger_fraction * delta_current
        current_direction = 1 if delta_current > 0 else -1
        t0 = _first_level_crossing(ts, currents, trigger_current, direction=current_direction)
        if t0 is None:
            continue

        force_0 = _interpolate_time(ts, fs, t0)
        x_0 = _interpolate_time(ts, xs, t0)
        velocity_0 = _interpolate_time(ts, velocities, t0)
        end_n = max(3, int(ceil(config.end_average_fraction * n)))
        force_100 = float(np.mean(fs[-end_n:]))
        delta_force = force_100 - force_0
        force_direction = 1 if delta_force > 0 else -1
        start_idx = int(np.searchsorted(ts, t0, side="left"))

        thresholds: dict[float, tuple[float, float | None]] = {}
        for fraction in (0.01, 0.63, 0.90):
            force_target = force_0 + fraction * delta_force
            crossing = _first_level_crossing(
                ts,
                fs,
                force_target,
                start_idx=start_idx,
                direction=force_direction,
            )
            thresholds[fraction] = (force_target, crossing)

        def elapsed_ms(crossing: float | None) -> float:
            return float((crossing - t0) * 1000.0) if crossing is not None else float("nan")

        t1 = thresholds[0.01][1]
        t63 = thresholds[0.63][1]
        t90 = thresholds[0.90][1]
        dt63_s = t63 - t0 if t63 is not None else float("nan")
        dt90_s = t90 - t0 if t90 is not None else float("nan")
        gradient63 = (
            abs(thresholds[0.63][0] - force_0) / dt63_s if np.isfinite(dt63_s) and dt63_s > 0 else float("nan")
        )
        gradient90 = (
            abs(thresholds[0.90][0] - force_0) / dt90_s if np.isfinite(dt90_s) and dt90_s > 0 else float("nan")
        )

        sample_rate = _sample_rate_hz(segment)
        issues: list[str] = []
        if config.standard == ResponseStandard.AUDI and sample_rate < 4000.0:
            issues.append(f"sample rate below Audi 4 kHz ({sample_rate:.2f} Hz)")
        if any(thresholds[fraction][1] is None for fraction in thresholds):
            issues.append("one or more force thresholds not crossed")
        local = segment[segment[TIME].between(t0 - 0.003, t0 + 0.003)][VELOCITY].abs()
        if len(local) >= 3 and float(local.mean()) > 0:
            speed_variation = float(local.std(ddof=0) / local.mean())
            if speed_variation > 0.10:
                issues.append("velocity variation around switching exceeds 10%")

        switch90 = elapsed_ms(t90)
        if config.t90_limit_ms is None:
            status = "Warning" if issues else "OK"
        elif not np.isfinite(switch90):
            status = "Invalid"
        else:
            status = "PASS" if switch90 <= config.t90_limit_ms else "FAIL"

        rows.append(
            {
                "Event ID": event_no,
                "OEM": config.standard.value.upper(),
                "Current Start A": current_start,
                "Current End A": current_end,
                "Current Delta A": delta_current,
                "Trigger Fraction": config.trigger_fraction,
                "Trigger Current A": trigger_current,
                "t0 s": t0,
                "Displacement at t0 mm": x_0,
                "Velocity at t0 m/s": velocity_0,
                "Direction": "Rebound" if velocity_0 > 0 else "Compression",
                "Force Change": "Build-up" if abs(force_100) > abs(force_0) else "Decay",
                "F0 N": force_0,
                "F100 N": force_100,
                "Delta F N": delta_force,
                "F1 N": thresholds[0.01][0],
                "F63 N": thresholds[0.63][0],
                "F90 N": thresholds[0.90][0],
                "Dead Time t1 ms": elapsed_ms(t1),
                "Switch Time t63 ms": elapsed_ms(t63),
                "Switch Time t90 ms": switch90,
                "Gradient 63 N/s": gradient63,
                "Gradient 90 N/s": gradient90,
                "Sample Rate Hz": sample_rate,
                "Segment Start s": float(ts[0]),
                "Segment End s": float(ts[-1]),
                "Status": status,
                "Issues": "; ".join(issues),
            }
        )

    events_frame = pd.DataFrame(rows)
    if events_frame.empty:
        raise ValueError("No valid current-step response event could be evaluated")

    settings = {
        "Analysis Mode": "Response Time",
        "OEM Profile": config.standard.value,
        "Trigger Fraction": config.trigger_fraction,
        "End Average Fraction": config.end_average_fraction,
        "t90 Limit ms": config.t90_limit_ms,
        "Source Format": dataset.source_format,
        "Source File": dataset.source_path.name,
        "Inferred Mapping": dataset.metadata.get("inferred_mapping"),
    }
    return ResponseAnalysisResult(data, events_frame, settings, dataset.source_path)


def _zero_crossings_for_direction(
    frame: pd.DataFrame,
    direction: Literal["Rebound", "Compression"],
    target_mm: float = 0.0,
    force_column: str = LOAD,
) -> tuple[list[float], list[float], list[float]]:
    t = frame[TIME].to_numpy(float)
    x = frame[DISP].to_numpy(float)
    force = frame[force_column].to_numpy(float)
    velocity = np.gradient(x, t) / 1000.0
    wanted = 1 if direction == "Rebound" else -1
    forces: list[float] = []
    speeds: list[float] = []
    times: list[float] = []
    for i in range(len(x) - 1):
        if (x[i] - target_mm) * (x[i + 1] - target_mm) > 0 or x[i] == x[i + 1]:
            continue
        local_velocity = (velocity[i] + velocity[i + 1]) / 2.0
        if local_velocity * wanted <= 0:
            continue
        q = (target_mm - x[i]) / (x[i + 1] - x[i])
        forces.append(float(force[i] + q * (force[i + 1] - force[i])))
        speeds.append(abs(float(velocity[i] + q * (velocity[i + 1] - velocity[i]))))
        times.append(float(t[i] + q * (t[i + 1] - t[i])))
    return forces, speeds, times


def _assign_sweep_directions(labels: list[float]) -> list[str]:
    directions: list[str] = []
    for i, label in enumerate(labels):
        previous = label - labels[i - 1] if i else 0.0
        following = labels[i + 1] - label if i + 1 < len(labels) else 0.0
        delta = previous if previous else following
        directions.append("Up" if delta > 0 else "Down" if delta < 0 else "Hold")
    return directions


def _bmw_hysteresis(dataset: DataSet, config: HysteresisConfig) -> HysteresisAnalysisResult:
    data = dataset.data.copy().sort_values(["Block ID", TIME]).reset_index(drop=True)
    block_groups = list(data.groupby("Block ID", sort=False))
    labels = [round(float(np.median(block[CURRENT])), config.current_decimals) for _, block in block_groups]
    sweep_directions = _assign_sweep_directions(labels)

    run_rows: list[dict[str, object]] = []
    for (block_id, block), current_label, sweep in zip(block_groups, labels, sweep_directions):
        for motion in ("Rebound", "Compression"):
            forces, speeds, times = _zero_crossings_for_direction(block, motion, config.zero_target_mm)
            if not forces:
                continue
            run_rows.append(
                {
                    "Block ID": block_id,
                    "Current Label A": current_label,
                    "Current Actual A": float(np.median(block[CURRENT])),
                    "Sweep Direction": sweep,
                    "Direction": motion,
                    "Force N": float(np.mean(forces)),
                    "Force SD N": float(np.std(forces, ddof=1)) if len(forces) > 1 else 0.0,
                    "Speed m/s": float(np.mean(speeds)),
                    "Crossing Count": len(forces),
                    "Crossing Time s": float(np.mean(times)),
                }
            )
    runs = pd.DataFrame(run_rows)
    if runs.empty:
        raise ValueError("No zero-displacement hysteresis measurement points were found")

    summary_rows: list[dict[str, object]] = []
    for (current_label, motion), group in runs.groupby(["Current Label A", "Direction"], sort=True):
        up = group[group["Sweep Direction"] == "Up"]
        down = group[group["Sweep Direction"] == "Down"]
        if up.empty or down.empty:
            continue
        increasing_force = float(up["Force N"].mean())
        decreasing_force = float(down["Force N"].mean())
        motion_sign = 1.0 if motion == "Rebound" else -1.0
        increasing_damping = increasing_force * motion_sign
        decreasing_damping = decreasing_force * motion_sign
        reference = (increasing_damping + decreasing_damping) / 2.0
        hysteresis_n = abs(increasing_damping - decreasing_damping)
        hysteresis_pct = hysteresis_n / reference * 100.0 if reference > 0 else float("nan")
        if config.limit_percent is None:
            status = "Not evaluated"
        elif np.isfinite(hysteresis_pct):
            status = "PASS" if hysteresis_pct <= config.limit_percent else "FAIL"
        else:
            status = "Invalid"
        summary_rows.append(
            {
                "Current A": current_label,
                "Direction": motion,
                "Increasing Force N": increasing_force,
                "Decreasing Force N": decreasing_force,
                "Reference Damping Force N": reference,
                "Hysteresis N": hysteresis_n,
                "Hysteresis %": hysteresis_pct,
                "Speed m/s": float(pd.concat([up["Speed m/s"], down["Speed m/s"]]).mean()),
                "Limit %": config.limit_percent,
                "Status": status,
            }
        )
    summary = pd.DataFrame(summary_rows)
    if summary.empty:
        raise ValueError("No paired increasing/decreasing current levels were found")

    settings = {
        "Analysis Mode": "Hysteresis",
        "OEM Profile": "bmw",
        "Stroke Requirement": "±50 mm",
        "Nominal Speeds m/s": "0.050 / 0.131 / 0.262 / 0.524 / 1.048",
        "Nominal Current Step A": "±0.2",
        "Zero Target mm": config.zero_target_mm,
        "Limit %": config.limit_percent,
        "Source File": dataset.source_path.name,
    }
    return HysteresisAnalysisResult(data, runs, summary, settings, dataset.source_path)


def _moving_average(values: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0 or len(values) < 3:
        return values.astype(float, copy=True)
    radius = min(radius, max(1, (len(values) - 1) // 2))
    padded = np.pad(values.astype(float), (radius, radius), mode="edge")
    kernel = np.ones(2 * radius + 1, dtype=float) / (2 * radius + 1)
    return np.convolve(padded, kernel, mode="valid")


def _samples_per_half_stroke(frame: pd.DataFrame) -> int:
    t = frame[TIME].to_numpy(float)
    x = frame[DISP].to_numpy(float)
    if len(x) < 5:
        return max(1, len(x) // 2)
    velocity = np.gradient(x, t)
    sign = np.sign(velocity)
    for i in range(1, len(sign)):
        if sign[i] == 0:
            sign[i] = sign[i - 1]
    reversal = np.where(sign[:-1] * sign[1:] < 0)[0] + 1
    if len(reversal) >= 2:
        return max(1, int(round(float(np.median(np.diff(reversal))))))
    return max(1, len(x) // 2)


def _nearest_state(current: float, mapping: dict[str, float]) -> str:
    return min(mapping, key=lambda state: abs(mapping[state] - current))


def _audi_state_mapping(plateaus: pd.DataFrame, config: HysteresisConfig) -> dict[str, float]:
    explicit = {
        "Soft": config.audi_soft_current_a,
        "KFM": config.audi_kfm_current_a,
        "Hard": config.audi_hard_current_a,
    }
    if all(value is not None for value in explicit.values()):
        return {state: float(value) for state, value in explicit.items() if value is not None}

    levels = sorted(float(value) for value in plateaus["Current Actual A"].unique())
    if len(levels) < 3:
        raise ValueError("Audi hysteresis requires at least three current states (soft / KFM / hard)")

    level_scores: list[tuple[float, float]] = []
    for level in levels:
        subset = plateaus[np.isclose(plateaus["Current Actual A"], level, atol=0.02)]
        normalized: list[float] = []
        for _, row in subset.iterrows():
            sign = 1.0 if row["Direction"] == "Rebound" else -1.0
            normalized.append(float(row["Mean Force N"]) * sign)
        if normalized:
            level_scores.append((float(np.mean(normalized)), level))
    if len(level_scores) < 3:
        raise ValueError("Could not infer Audi soft/KFM/hard states from damping-force levels")
    level_scores.sort()
    return {
        "Soft": level_scores[0][1],
        "KFM": level_scores[len(level_scores) // 2][1],
        "Hard": level_scores[-1][1],
    }


def _audi_hysteresis(dataset: DataSet, config: HysteresisConfig) -> HysteresisAnalysisResult:
    data = dataset.data.copy().sort_values(["Block ID", TIME]).reset_index(drop=True)
    run_rows: list[dict[str, object]] = []
    processed_blocks: list[pd.DataFrame] = []

    for block_order, (block_id, raw_block) in enumerate(data.groupby("Block ID", sort=False), start=1):
        block = raw_block.copy().reset_index(drop=True)
        half_stroke_samples = _samples_per_half_stroke(block)
        radius = max(1, int(round(config.audi_smoothing_fraction_per_side * half_stroke_samples)))
        block["Smoothed Axial Load"] = _moving_average(block[LOAD].to_numpy(float), radius)
        block["Audi Smoothing Radius Samples"] = radius
        block["Audi Block Order"] = block_order
        processed_blocks.append(block)

        current_actual = float(np.median(block[CURRENT]))
        for motion in ("Rebound", "Compression"):
            forces, speeds, times = _zero_crossings_for_direction(
                block,
                motion,
                config.zero_target_mm,
                force_column="Smoothed Axial Load",
            )
            if not forces:
                continue
            first_force = float(forces[0])
            retained = forces[1:]  # first cycle after switching is excluded from the mean
            issues: list[str] = []
            if len(retained) < config.audi_min_mean_cycles:
                issues.append(
                    f"only {len(retained)} retained cycles; Audi requires at least {config.audi_min_mean_cycles}"
                )
            mean_force = float(np.mean(retained)) if retained else float("nan")
            mean_speed = float(np.mean(speeds[1:])) if len(speeds) > 1 else float(np.mean(speeds))
            run_rows.append(
                {
                    "Block ID": block_id,
                    "Block Order": block_order,
                    "Current Actual A": current_actual,
                    "Direction": motion,
                    "Crossing Count": len(forces),
                    "Retained Cycle Count": len(retained),
                    "First Cycle Force N": first_force,
                    "Mean Force N": mean_force,
                    "Speed m/s": mean_speed,
                    "Smoothing Radius Samples": radius,
                    "Status": "Warning" if issues else "OK",
                    "Issues": "; ".join(issues),
                }
            )

    plateaus = pd.DataFrame(run_rows)
    if plateaus.empty:
        raise ValueError("No Audi hysteresis center-stroke force points were found")

    state_mapping = _audi_state_mapping(plateaus, config)
    plateaus["State"] = plateaus["Current Actual A"].map(lambda value: _nearest_state(float(value), state_mapping))

    spread_by_direction: dict[str, float] = {}
    for motion in ("Rebound", "Compression"):
        subset = plateaus[(plateaus["Direction"] == motion) & plateaus["Mean Force N"].notna()]
        sign = 1.0 if motion == "Rebound" else -1.0
        state_means = subset.groupby("State")["Mean Force N"].mean() * sign
        if "Hard" in state_means and "Soft" in state_means:
            spread_by_direction[motion] = float(state_means["Hard"] - state_means["Soft"])

    summary_rows: list[dict[str, object]] = []
    kfm_orders = sorted(plateaus.loc[plateaus["State"] == "KFM", "Block Order"].unique())
    for before_order, after_order in zip(kfm_orders[:-1], kfm_orders[1:]):
        between = plateaus[
            (plateaus["Block Order"] > before_order)
            & (plateaus["Block Order"] < after_order)
            & (plateaus["State"] != "KFM")
        ]
        excursion_states = [state for state in between["State"].dropna().unique() if state in {"Soft", "Hard"}]
        if not excursion_states:
            continue
        excursion_state = excursion_states[0]
        excursion_order_candidates = sorted(between.loc[between["State"] == excursion_state, "Block Order"].unique())
        if not excursion_order_candidates:
            continue
        excursion_order = excursion_order_candidates[0]

        for motion in ("Rebound", "Compression"):
            before = plateaus[(plateaus["Block Order"] == before_order) & (plateaus["Direction"] == motion)]
            after = plateaus[(plateaus["Block Order"] == after_order) & (plateaus["Direction"] == motion)]
            excursion = plateaus[(plateaus["Block Order"] == excursion_order) & (plateaus["Direction"] == motion)]
            if before.empty or after.empty or excursion.empty:
                continue
            before_force = float(before["Mean Force N"].iloc[0])
            after_force = float(after["Mean Force N"].iloc[0])
            first_cycle_force = float(excursion["First Cycle Force N"].iloc[0])
            hysteresis_n = abs(after_force - before_force)
            spread = spread_by_direction.get(motion, float("nan"))
            hysteresis_pct = hysteresis_n / spread * 100.0 if np.isfinite(spread) and spread > 0 else float("nan")
            first_cycle_delta = first_cycle_force - before_force
            if config.limit_percent is None:
                status = "Not evaluated"
            elif np.isfinite(hysteresis_pct):
                status = "PASS" if hysteresis_pct <= config.limit_percent else "FAIL"
            else:
                status = "Invalid"
            summary_rows.append(
                {
                    "Excursion State": excursion_state,
                    "Direction": motion,
                    "KFM Before Block": int(before_order),
                    "Extreme Block": int(excursion_order),
                    "KFM After Block": int(after_order),
                    "KFM Before Force N": before_force,
                    "KFM After Force N": after_force,
                    "Hysteresis N": hysteresis_n,
                    "Spread Fmax-Fmin N": spread,
                    "Hysteresis %": hysteresis_pct,
                    "First Cycle Force N": first_cycle_force,
                    "First Cycle Delta N": first_cycle_delta,
                    "Limit %": config.limit_percent,
                    "Status": status,
                }
            )

    summary = pd.DataFrame(summary_rows)
    if summary.empty:
        raise ValueError(
            "Audi hysteresis could not pair KFM-before / extreme / KFM-after plateaus. "
            "Verify current-state mapping and switching sequence."
        )

    processed = pd.concat(processed_blocks, ignore_index=True)
    settings = {
        "Analysis Mode": "Hysteresis",
        "OEM Profile": "audi",
        "Smoothing": f"moving average ±{config.audi_smoothing_fraction_per_side * 100:.1f}% samples per stroke",
        "First Cycle Excluded": True,
        "Minimum Mean Cycles": config.audi_min_mean_cycles,
        "State Mapping A": state_mapping,
        "Limit %": config.limit_percent,
        "Source File": dataset.source_path.name,
    }
    return HysteresisAnalysisResult(processed, plateaus, summary, settings, dataset.source_path)


def analyze_hysteresis(dataset: DataSet, config: HysteresisConfig | None = None) -> HysteresisAnalysisResult:
    config = config or HysteresisConfig()
    if config.standard == HysteresisStandard.BMW:
        return _bmw_hysteresis(dataset, config)
    if config.standard == HysteresisStandard.AUDI:
        return _audi_hysteresis(dataset, config)
    raise ValueError(f"Unsupported hysteresis standard: {config.standard}")
