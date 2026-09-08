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

BMW_TARGET_SPEEDS = (0.0131, 0.524, 1.048)
AUDI_TARGET_SPEEDS = (0.052, 0.131, 0.262, 0.524)


def _smooth_current(values: np.ndarray) -> np.ndarray:
    window = 5 if len(values) >= 25 else 3
    return pd.Series(values).rolling(window, center=True, min_periods=1).median().to_numpy(float)


def _current_step_candidates(t: np.ndarray, current: np.ndarray, config: ResponseConfig) -> list[tuple[int, int, int]]:
    if len(current) < 8:
        return []
    smooth = _smooth_current(current)
    slope = np.abs(np.gradient(smooth, t))
    finite = slope[np.isfinite(slope)]
    if not len(finite):
        return []
    peak = float(np.max(finite))
    if not np.isfinite(peak) or peak <= 0:
        return []
    median = float(np.median(finite))
    mad = float(np.median(np.abs(finite - median)))
    threshold = max(config.event_derivative_fraction * peak, median + 8.0 * max(mad, 1e-12))
    mask = slope >= threshold

    groups: list[tuple[int, int, int]] = []
    start: int | None = None
    for idx, active in enumerate(mask):
        if active and start is None:
            start = idx
        elif not active and start is not None:
            end = idx - 1
            peak_idx = start + int(np.argmax(slope[start : end + 1]))
            groups.append((start, end, peak_idx))
            start = None
    if start is not None:
        end = len(mask) - 1
        peak_idx = start + int(np.argmax(slope[start : end + 1]))
        groups.append((start, end, peak_idx))

    merged: list[tuple[int, int, int]] = []
    for group in groups:
        if not merged:
            merged.append(group)
            continue
        previous = merged[-1]
        if t[group[2]] - t[previous[2]] < config.min_event_separation_s:
            left, right = previous[0], group[1]
            peak_idx = left + int(np.argmax(slope[left : right + 1]))
            merged[-1] = (left, right, peak_idx)
        else:
            merged.append(group)
    return merged


def _verify_steps(frame: pd.DataFrame, config: ResponseConfig) -> list[dict[str, float | int]]:
    t = frame[TIME].to_numpy(float)
    current = frame[CURRENT].to_numpy(float)
    groups = _current_step_candidates(t, current, config)
    if not groups:
        return []
    dt = np.diff(t)
    dt = dt[np.isfinite(dt) & (dt > 0)]
    median_dt = float(np.median(dt)) if len(dt) else 0.001
    plateau_n = max(5, int(round(0.006 / max(median_dt, 1e-9))))
    gap_n = max(1, int(round(0.0005 / max(median_dt, 1e-9))))

    verified: list[dict[str, float | int]] = []
    for group_start, group_end, peak_idx in groups:
        pre_end = max(0, group_start - gap_n)
        pre_start = max(0, pre_end - plateau_n)
        post_start = min(len(frame), group_end + gap_n + 1)
        post_end = min(len(frame), post_start + plateau_n)
        if pre_end - pre_start < 3 or post_end - post_start < 3:
            continue
        current_start = float(np.median(current[pre_start:pre_end]))
        current_end = float(np.median(current[post_start:post_end]))
        if abs(current_end - current_start) < config.min_current_step_a:
            continue
        verified.append(
            {
                "group_start": group_start,
                "group_end": group_end,
                "peak_idx": peak_idx,
                "current_start": current_start,
                "current_end": current_end,
                "pre_start": pre_start,
                "post_end": post_end,
            }
        )
    return verified


def _same_force_sign_window(force: np.ndarray, center: int, lower: int, upper: int) -> tuple[int, int]:
    sign = 1 if float(force[center]) >= 0 else -1
    magnitude = np.abs(force)
    guard = max(5.0, float(np.nanpercentile(magnitude, 10)) * 0.05)
    left = center
    while left > lower:
        value = float(force[left - 1])
        if abs(value) > guard and (1 if value >= 0 else -1) != sign:
            break
        left -= 1
    right = center
    while right < upper:
        value = float(force[right + 1])
        if abs(value) > guard and (1 if value >= 0 else -1) != sign:
            break
        right += 1
    return left, right


def _snap_target_speed(standard: ResponseStandard, measured_abs: float) -> float:
    targets = BMW_TARGET_SPEEDS if standard == ResponseStandard.BMW else AUDI_TARGET_SPEEDS
    nearest = min(targets, key=lambda value: abs(value - measured_abs))
    tolerance = max(0.015, 0.20 * nearest)
    return float(nearest) if abs(nearest - measured_abs) <= tolerance else float("nan")


def _state_map(events: pd.DataFrame) -> dict[float, str]:
    if events.empty:
        return {}
    values: list[tuple[float, float]] = []
    all_currents = pd.concat([events["Current Start A"], events["Current End A"]], ignore_index=True)
    rounded = sorted({round(float(value), 2) for value in all_currents if np.isfinite(value)})
    for current in rounded:
        samples: list[float] = []
        for _, row in events.iterrows():
            if abs(round(float(row["Current Start A"]), 2) - current) < 1e-9:
                samples.append(abs(float(row["F0 N"])))
            if abs(round(float(row["Current End A"]), 2) - current) < 1e-9:
                samples.append(abs(float(row["F100 N"])))
        if samples:
            values.append((current, float(np.mean(samples))))
    if len(values) < 3:
        return {}
    values.sort(key=lambda item: item[1])
    labels = ["Soft"] + (["Medium"] * max(0, len(values) - 2)) + ["Hard"]
    return {current: labels[index] for index, (current, _) in enumerate(values)}


def _elapsed_ms(crossing: float | None, t0: float) -> float:
    if crossing is None or crossing < t0:
        return float("nan")
    return float((crossing - t0) * 1000.0)


def _evaluate_block(block: pd.DataFrame, block_id: int, config: ResponseConfig, event_id_start: int) -> list[dict[str, object]]:
    block = block[[TIME, DISP, LOAD, CURRENT]].dropna().sort_values(TIME).reset_index(drop=True).copy()
    if len(block) < 8:
        return []
    t = block[TIME].to_numpy(float)
    if np.any(np.diff(t) <= 0):
        return []
    x = block[DISP].to_numpy(float)
    force = block[LOAD].to_numpy(float)
    current = block[CURRENT].to_numpy(float)
    block[VELOCITY] = np.gradient(x, t) / 1000.0
    velocity = block[VELOCITY].to_numpy(float)

    steps = _verify_steps(block, config)
    if not steps:
        slope = np.abs(np.gradient(_smooth_current(current), t))
        peak_idx = int(np.argmax(slope))
        n = len(block)
        plateau_n = max(3, int(round(config.plateau_fraction * n)))
        current_start = float(np.median(current[:plateau_n]))
        current_end = float(np.median(current[-plateau_n:]))
        if abs(current_end - current_start) >= config.min_current_step_a:
            steps = [{
                "group_start": max(0, peak_idx - 1),
                "group_end": min(n - 1, peak_idx + 1),
                "peak_idx": peak_idx,
                "current_start": current_start,
                "current_end": current_end,
                "pre_start": 0,
                "post_end": n,
            }]
    if not steps:
        return []

    centers = [int(step["peak_idx"]) for step in steps]
    coarse = [0]
    coarse.extend((left + right) // 2 for left, right in zip(centers[:-1], centers[1:]))
    coarse.append(len(block) - 1)

    rows: list[dict[str, object]] = []
    for local_no, step in enumerate(steps):
        center = int(step["peak_idx"])
        lower, upper = coarse[local_no], coarse[local_no + 1]
        left, right = _same_force_sign_window(force, center, lower, upper)
        if right - left + 1 < 8:
            left, right = lower, upper
        segment = block.iloc[left : right + 1].reset_index(drop=True)
        ts = segment[TIME].to_numpy(float)
        xs = segment[DISP].to_numpy(float)
        fs = segment[LOAD].to_numpy(float)
        currents = segment[CURRENT].to_numpy(float)
        velocities = segment[VELOCITY].to_numpy(float)

        current_start = float(step["current_start"])
        current_end = float(step["current_end"])
        delta_current = current_end - current_start
        trigger_current = current_start + config.trigger_fraction * delta_current
        t0 = _first_level_crossing(ts, currents, trigger_current, direction=1 if delta_current > 0 else -1)
        if t0 is None:
            continue
        force_0 = _interpolate_time(ts, fs, t0)
        x_0 = _interpolate_time(ts, xs, t0)
        velocity_0 = _interpolate_time(ts, velocities, t0)
        direction = "Rebound" if force_0 >= 0 else "Compression"
        velocity_direction = "Rebound" if velocity_0 > 0 else "Compression"

        end_n = max(3, int(ceil(config.end_average_fraction * len(segment))))
        end_n = min(end_n, max(3, len(segment) // 3))
        force_100 = float(np.mean(fs[-end_n:]))
        delta_force = force_100 - force_0
        if abs(delta_force) < 1e-9:
            continue
        force_direction = 1 if delta_force > 0 else -1

        after_mask = ts > t0
        response_t = np.concatenate(([t0], ts[after_mask]))
        response_f = np.concatenate(([force_0], fs[after_mask]))
        thresholds: dict[float, tuple[float, float | None]] = {}
        for fraction in (0.01, 0.10, 0.63, 0.90):
            target = force_0 + fraction * delta_force
            crossing = _first_level_crossing(response_t, response_f, target, start_idx=0, direction=force_direction)
            thresholds[fraction] = (target, crossing)

        t1 = thresholds[0.01][1]
        t10 = thresholds[0.10][1]
        t63 = thresholds[0.63][1]
        t90 = thresholds[0.90][1]
        dt63_s = (t63 - t0) if t63 is not None else float("nan")
        dt90_s = (t90 - t0) if t90 is not None else float("nan")
        gradient63 = abs(thresholds[0.63][0] - force_0) / dt63_s if np.isfinite(dt63_s) and dt63_s > 0 else float("nan")
        gradient90 = abs(thresholds[0.90][0] - force_0) / dt90_s if np.isfinite(dt90_s) and dt90_s > 0 else float("nan")

        sample_rate = _sample_rate_hz(segment)
        issues: list[str] = []
        if config.standard == ResponseStandard.AUDI and np.isfinite(sample_rate) and sample_rate < 4000.0:
            issues.append(f"sample rate below Audi 4 kHz ({sample_rate:.2f} Hz)")
        if direction != velocity_direction:
            issues.append("load sign and displacement direction disagree")
        if any(value[1] is None for value in thresholds.values()):
            issues.append("one or more force thresholds not crossed")
        local = segment[segment[TIME].between(t0 - 0.003, t0 + 0.003)][VELOCITY].abs()
        if len(local) >= 3 and float(local.mean()) > 0:
            speed_variation = float(local.std(ddof=0) / local.mean())
            if speed_variation > 0.10:
                issues.append("velocity variation around switching exceeds 10%")

        measured_speed = abs(float(velocity_0))
        target_speed = _snap_target_speed(config.standard, measured_speed)
        signed_target_speed = np.sign(velocity_0) * target_speed if np.isfinite(target_speed) else float("nan")
        switch90 = _elapsed_ms(t90, t0)
        if config.t90_limit_ms is None:
            status = "Warning" if issues else "OK"
        elif not np.isfinite(switch90):
            status = "Invalid"
        else:
            status = "PASS" if switch90 <= config.t90_limit_ms else "FAIL"

        start_window_end = min(len(segment) - 1, max(1, end_n - 1))
        end_window_start = max(0, len(segment) - end_n)
        rows.append({
            "Event ID": event_id_start + local_no,
            "Block ID": block_id,
            "OEM": config.standard.value.upper(),
            "Stage": "",
            "Current Start A": current_start,
            "Current End A": current_end,
            "Current Delta A": delta_current,
            "Trigger Fraction": config.trigger_fraction,
            "Trigger Current A": trigger_current,
            "t0 s": t0,
            "Displacement at t0 mm": x_0,
            "Velocity at t0 m/s": velocity_0,
            "Target Velocity m/s": signed_target_speed,
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
            "Segment Start s": float(ts[0]),
            "Segment End s": float(ts[-1]),
            "Force Start Window Start s": float(ts[0]),
            "Force Start Window End s": float(ts[start_window_end]),
            "Force End Window Start s": float(ts[end_window_start]),
            "Force End Window End s": float(ts[-1]),
            "Status": status,
            "Issues": "; ".join(issues),
        })
    return rows


def analyze_response_time_multistage(dataset: DataSet, config: ResponseConfig | None = None) -> ResponseAnalysisResult:
    config = config or ResponseConfig()
    if not 0 < config.trigger_fraction < 1:
        raise ValueError("Trigger fraction must be between 0 and 1")
    if not 0 < config.end_average_fraction <= 0.5:
        raise ValueError("End-average fraction must be in (0, 0.5]")
    required = [TIME, DISP, LOAD, CURRENT]
    missing = [column for column in required if column not in dataset.data.columns]
    if missing:
        raise ValueError(f"Missing dynamic response channel(s): {', '.join(missing)}")

    source = dataset.data.copy()
    block_groups = list(source.groupby("Block ID", sort=False)) if "Block ID" in source.columns else [(1, source)]
    processed_parts: list[pd.DataFrame] = []
    rows: list[dict[str, object]] = []
    next_event_id = 1
    for block_id, raw in block_groups:
        block = raw.copy().sort_values(TIME).reset_index(drop=True)
        valid = block[required].dropna().copy()
        if len(valid) < 8:
            continue
        t = valid[TIME].to_numpy(float)
        if np.any(np.diff(t) <= 0):
            continue
        valid[VELOCITY] = np.gradient(valid[DISP].to_numpy(float), t) / 1000.0
        valid["Block ID"] = int(block_id)
        processed_parts.append(valid)
        block_rows = _evaluate_block(valid, int(block_id), config, next_event_id)
        rows.extend(block_rows)
        next_event_id += len(block_rows)

    events = pd.DataFrame(rows)
    if events.empty:
        raise ValueError("No valid current-step response event could be evaluated")

    mapping = _state_map(events)
    if mapping:
        def stage_name(row: pd.Series) -> str:
            start = mapping.get(round(float(row["Current Start A"]), 2))
            end = mapping.get(round(float(row["Current End A"]), 2))
            if start and end:
                return f"{start} → {end}"
            return f"{float(row['Current Start A']):.2f} A → {float(row['Current End A']):.2f} A"
        events["Stage"] = events.apply(stage_name, axis=1)
    else:
        events["Stage"] = events.apply(
            lambda row: f"{float(row['Current Start A']):.2f} A → {float(row['Current End A']):.2f} A",
            axis=1,
        )

    processed = pd.concat(processed_parts, ignore_index=True) if processed_parts else source
    settings = {
        "Analysis Mode": "Response Time - Full File Multi-stage",
        "OEM Profile": config.standard.value,
        "Trigger Fraction": config.trigger_fraction,
        "End Average Fraction": config.end_average_fraction,
        "t90 Limit ms": config.t90_limit_ms,
        "Source Format": dataset.source_format,
        "Source File": dataset.source_path.name,
        "Detected Events": len(events),
        "Inferred Mapping": (dataset.metadata or {}).get("inferred_mapping"),
    }
    return ResponseAnalysisResult(processed, events, settings, dataset.source_path)
