from __future__ import annotations

from math import ceil

import numpy as np
import pandas as pd

from .dynamic_analysis import (
    CURRENT,
    DISP,
    LOAD,
    TIME,
    VELOCITY,
    ResponseAnalysisResult,
    ResponseConfig,
    ResponseStandard,
    _first_level_crossing,
    _interpolate_time,
    _sample_rate_hz,
)
from .parser import DataSet
from .response_multistage import (
    AUDI_TARGET_SPEEDS,
    BMW_TARGET_SPEEDS,
    analyze_response_time_multistage,
)

TARGET_SPEED_REL_TOLERANCE = 0.10
TARGET_SPEED_ABS_FLOOR_M_S = 0.005
TARGET_LOCAL_WINDOW_S = 0.003
TARGET_MASK_SMOOTHING_S = 0.001
TARGET_MASK_GAP_BRIDGE_S = 0.001
MIN_TARGET_POST_WINDOW_S = 0.006


def _target_speeds(standard: ResponseStandard) -> tuple[float, ...]:
    return BMW_TARGET_SPEEDS if standard == ResponseStandard.BMW else AUDI_TARGET_SPEEDS


def _target_tolerance(target_m_s: float) -> float:
    return max(TARGET_SPEED_ABS_FLOOR_M_S, TARGET_SPEED_REL_TOLERANCE * abs(float(target_m_s)))


def _match_target_speed(standard: ResponseStandard, measured_abs_m_s: float) -> float:
    if not np.isfinite(measured_abs_m_s):
        return float("nan")
    nearest = min(_target_speeds(standard), key=lambda value: abs(float(value) - measured_abs_m_s))
    return float(nearest) if abs(float(nearest) - measured_abs_m_s) <= _target_tolerance(nearest) else float("nan")


def _odd_sample_count(duration_s: float, median_dt_s: float, minimum: int = 3) -> int:
    count = max(minimum, int(round(float(duration_s) / max(float(median_dt_s), 1e-12))))
    if count % 2 == 0:
        count += 1
    return count


def _bridge_short_false_gaps(mask: np.ndarray, max_gap: int) -> np.ndarray:
    out = np.asarray(mask, dtype=bool).copy()
    if max_gap <= 0 or len(out) < 3:
        return out
    start = None
    for index, value in enumerate(out):
        if not value and start is None:
            start = index
        elif value and start is not None:
            end = index - 1
            if start > 0 and end - start + 1 <= max_gap and out[start - 1]:
                out[start : end + 1] = True
            start = None
    return out


def _local_target_speed_stats(frame: pd.DataFrame, t0: float) -> tuple[float, float, float]:
    local = frame[frame[TIME].between(float(t0) - TARGET_LOCAL_WINDOW_S, float(t0) + TARGET_LOCAL_WINDOW_S)]
    if local.empty or VELOCITY not in local.columns:
        return float("nan"), float("nan"), float("nan")
    values = local[VELOCITY].to_numpy(float)
    values = values[np.isfinite(values)]
    if not len(values):
        return float("nan"), float("nan"), float("nan")
    abs_values = np.abs(values)
    median_abs = float(np.median(abs_values))
    mean_abs = float(np.mean(abs_values))
    variation = float(np.std(abs_values, ddof=0) / mean_abs) if mean_abs > 1e-12 else float("nan")
    signed_median = float(np.sign(np.median(values)) * median_abs)
    return median_abs, signed_median, variation


def _target_velocity_window(frame: pd.DataFrame, t0: float, target_m_s: float) -> tuple[int, int] | None:
    if frame.empty or VELOCITY not in frame.columns:
        return None
    t = frame[TIME].to_numpy(float)
    velocity = frame[VELOCITY].to_numpy(float)
    finite_dt = np.diff(t)
    finite_dt = finite_dt[np.isfinite(finite_dt) & (finite_dt > 0)]
    if not len(finite_dt):
        return None
    median_dt = float(np.median(finite_dt))
    smooth_n = _odd_sample_count(TARGET_MASK_SMOOTHING_S, median_dt)
    smooth_abs = (
        pd.Series(np.abs(velocity))
        .rolling(smooth_n, center=True, min_periods=1)
        .median()
        .to_numpy(float)
    )
    tolerance = _target_tolerance(target_m_s)
    mask = np.isfinite(smooth_abs) & (np.abs(smooth_abs - float(target_m_s)) <= tolerance)
    gap_n = max(1, int(round(TARGET_MASK_GAP_BRIDGE_S / max(median_dt, 1e-12))))
    mask = _bridge_short_false_gaps(mask, gap_n)

    center = int(np.argmin(np.abs(t - float(t0))))
    if not mask[center]:
        nearby = np.flatnonzero(mask & (np.abs(t - float(t0)) <= max(0.0015, 3.0 * median_dt)))
        if not len(nearby):
            return None
        center = int(nearby[np.argmin(np.abs(t[nearby] - float(t0)))])

    left = center
    while left > 0 and mask[left - 1]:
        left -= 1
    right = center
    while right + 1 < len(mask) and mask[right + 1]:
        right += 1
    return left, right


def _elapsed_ms(crossing: float | None, t0: float) -> float:
    if crossing is None or crossing < t0:
        return float("nan")
    return float((crossing - t0) * 1000.0)


def _recalculate_in_target_window(
    row: pd.Series,
    processed: pd.DataFrame,
    config: ResponseConfig,
    new_event_id: int,
) -> dict[str, object] | None:
    block = processed.copy()
    if "Block ID" in block.columns and "Block ID" in row.index:
        block = block[block["Block ID"] == int(row["Block ID"])]
    block = block[
        block[TIME].between(float(row["Segment Start s"]), float(row["Segment End s"]))
    ].copy().sort_values(TIME).reset_index(drop=True)
    if len(block) < 8:
        return None
    if VELOCITY not in block.columns:
        t = block[TIME].to_numpy(float)
        block[VELOCITY] = np.gradient(block[DISP].to_numpy(float), t) / 1000.0

    t0 = float(row["t0 s"])
    measured_abs, measured_signed, speed_variation = _local_target_speed_stats(block, t0)
    target_abs = _match_target_speed(config.standard, measured_abs)
    if not np.isfinite(target_abs):
        return None

    window = _target_velocity_window(block, t0, target_abs)
    if window is None:
        return None
    left, right = window
    target_segment = block.iloc[left : right + 1].copy().reset_index(drop=True)
    if len(target_segment) < 8:
        return None
    ts = target_segment[TIME].to_numpy(float)
    if not (float(ts[0]) <= t0 <= float(ts[-1])):
        return None
    if float(ts[-1]) - t0 < MIN_TARGET_POST_WINDOW_S:
        return None

    fs = target_segment[LOAD].to_numpy(float)
    xs = target_segment[DISP].to_numpy(float)
    currents = target_segment[CURRENT].to_numpy(float)
    velocities = target_segment[VELOCITY].to_numpy(float)

    current_start = float(row["Current Start A"])
    current_end = float(row["Current End A"])
    delta_current = current_end - current_start
    trigger_current = current_start + config.trigger_fraction * delta_current
    recalc_t0 = _first_level_crossing(
        ts,
        currents,
        trigger_current,
        direction=1 if delta_current > 0 else -1,
    )
    if recalc_t0 is None:
        return None
    t0 = float(recalc_t0)
    force_0 = _interpolate_time(ts, fs, t0)
    x_0 = _interpolate_time(ts, xs, t0)
    velocity_0 = _interpolate_time(ts, velocities, t0)

    end_n = max(3, int(ceil(config.end_average_fraction * len(target_segment))))
    end_n = min(end_n, max(3, len(target_segment) // 3))
    force_100 = float(np.mean(fs[-end_n:]))
    delta_force = force_100 - force_0
    if abs(delta_force) < 1e-9:
        return None
    force_direction = 1 if delta_force > 0 else -1

    response_mask = ts > t0
    response_t = np.concatenate(([t0], ts[response_mask]))
    response_f = np.concatenate(([force_0], fs[response_mask]))
    thresholds: dict[float, tuple[float, float | None]] = {}
    for fraction in (0.01, 0.10, 0.63, 0.90):
        target_force = force_0 + float(fraction) * delta_force
        crossing = _first_level_crossing(
            response_t,
            response_f,
            target_force,
            start_idx=0,
            direction=force_direction,
        )
        thresholds[fraction] = (target_force, crossing)

    t1 = thresholds[0.01][1]
    t10 = thresholds[0.10][1]
    t63 = thresholds[0.63][1]
    t90 = thresholds[0.90][1]
    dt63 = (t63 - t0) if t63 is not None else float("nan")
    dt90 = (t90 - t0) if t90 is not None else float("nan")
    gradient63 = (
        abs(thresholds[0.63][0] - force_0) / dt63
        if np.isfinite(dt63) and dt63 > 0
        else float("nan")
    )
    gradient90 = (
        abs(thresholds[0.90][0] - force_0) / dt90
        if np.isfinite(dt90) and dt90 > 0
        else float("nan")
    )

    direction = "Rebound" if force_0 >= 0 else "Compression"
    velocity_direction = "Rebound" if velocity_0 > 0 else "Compression"
    signed_target = float(np.sign(velocity_0) * target_abs)
    deviation_pct = abs(measured_abs - target_abs) / target_abs * 100.0 if target_abs > 0 else float("nan")

    sample_rate = _sample_rate_hz(target_segment)
    issues: list[str] = []
    if config.standard == ResponseStandard.AUDI and np.isfinite(sample_rate) and sample_rate < 4000.0:
        issues.append(f"sample rate below Audi 4 kHz ({sample_rate:.2f} Hz)")
    if direction != velocity_direction:
        issues.append("load sign and displacement direction disagree")
    if any(value[1] is None for value in thresholds.values()):
        issues.append("one or more force thresholds not crossed inside target-speed window")
    if np.isfinite(speed_variation) and speed_variation > 0.10:
        issues.append("velocity variation around switching exceeds 10%")

    switch90 = _elapsed_ms(t90, t0)
    if config.t90_limit_ms is None:
        status = "Warning" if issues else "OK"
    elif not np.isfinite(switch90):
        status = "Invalid"
    else:
        status = "PASS" if switch90 <= config.t90_limit_ms else "FAIL"

    out = dict(row)
    out.update(
        {
            "Raw Event ID": int(row["Event ID"]),
            "Event ID": int(new_event_id),
            "Trigger Current A": trigger_current,
            "t0 s": t0,
            "Displacement at t0 mm": x_0,
            "Velocity at t0 m/s": velocity_0,
            "Evaluation Velocity m/s": measured_signed,
            "Target Velocity m/s": signed_target,
            "Target Velocity Deviation %": deviation_pct,
            "Direction": direction,
            "Force Change": "Build-up" if abs(force_100) > abs(force_0) else "Decay",
            "F0 N": force_0,
            "F1 N": thresholds[0.01][0],
            "F10 N": thresholds[0.10][0],
            "F63 N": thresholds[0.63][0],
            "F90 N": thresholds[0.90][0],
            "F100 N": force_100,
            "Delta F N": delta_force,
            "Dead Time t1 ms": _elapsed_ms(t1, t0),
            "Switch Time t10 ms": _elapsed_ms(t10, t0),
            "Switch Time t63 ms": _elapsed_ms(t63, t0),
            "Switch Time t90 ms": switch90,
            "t1 s": float(t1) if t1 is not None else float("nan"),
            "t10 s": float(t10) if t10 is not None else float("nan"),
            "t63 s": float(t63) if t63 is not None else float("nan"),
            "t90 s": float(t90) if t90 is not None else float("nan"),
            "Gradient 63 N/s": gradient63,
            "Gradient 90 N/s": gradient90,
            "Sample Rate Hz": sample_rate,
            "Raw Segment Start s": float(row["Segment Start s"]),
            "Raw Segment End s": float(row["Segment End s"]),
            "Segment Start s": float(ts[0]),
            "Segment End s": float(ts[-1]),
            "Target Window Start s": float(ts[0]),
            "Target Window End s": float(ts[-1]),
            "Force Start Window Start s": float(ts[0]),
            "Force Start Window End s": float(ts[min(len(ts) - 1, max(1, end_n - 1))]),
            "Force End Window Start s": float(ts[max(0, len(ts) - end_n)]),
            "Force End Window End s": float(ts[-1]),
            "Status": status,
            "Issues": "; ".join(issues),
        }
    )
    return out


def analyze_response_time_target_velocity(
    dataset: DataSet,
    config: ResponseConfig | None = None,
) -> ResponseAnalysisResult:
    """Analyze only current-step events that occur inside an OEM target-speed window.

    The base full-file detector still finds every valid current step. This layer then
    rejects current changes that occur away from the specified BMW/Audi response
    speeds and recalculates F100/F1/F10/F63/F90 plus t1/t10/t63/t90 using only the
    contiguous constant-speed window around the switch. This prevents a reversal or
    acceleration portion of the stroke from becoming the response endpoint.
    """

    config = config or ResponseConfig()
    base = analyze_response_time_multistage(dataset, config)
    accepted: list[dict[str, object]] = []
    for _, row in base.events.iterrows():
        recalculated = _recalculate_in_target_window(
            row,
            base.processed,
            config,
            new_event_id=len(accepted) + 1,
        )
        if recalculated is not None:
            accepted.append(recalculated)

    if not accepted:
        targets = ", ".join(f"{value:g}" for value in _target_speeds(config.standard))
        raise ValueError(
            "未找到目标速度附近的有效响应事件 / "
            f"No valid response event near OEM target speed(s): {targets} m/s"
        )

    events = pd.DataFrame(accepted)
    settings = dict(base.settings)
    settings.update(
        {
            "Response Evaluation": "OEM target-speed window only",
            "OEM Target Speeds m/s": _target_speeds(config.standard),
            "Target Speed Relative Tolerance": TARGET_SPEED_REL_TOLERANCE,
            "Target Speed Absolute Floor m/s": TARGET_SPEED_ABS_FLOOR_M_S,
            "Detected Raw Events": int(len(base.events)),
            "Accepted Target-Speed Events": int(len(events)),
            "Rejected Non-target Events": int(len(base.events) - len(events)),
        }
    )
    return ResponseAnalysisResult(base.processed, events, settings, base.source_path)
