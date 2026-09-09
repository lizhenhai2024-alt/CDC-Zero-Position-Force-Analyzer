from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from cdc_analyzer.dynamic_analysis import (
    CURRENT,
    DISP,
    LOAD,
    TIME,
    VELOCITY,
    ResponseConfig,
    ResponseStandard,
)
from cdc_analyzer.parser import DataSet
from cdc_analyzer.response_v074 import (
    _event_boundaries,
    _target_speed_component,
    analyze_response_time_v074,
)


def _dataset(frame: pd.DataFrame, name: str = "synthetic.dat") -> DataSet:
    return DataSet(frame, Path(name), "synthetic")


def _three_speed_events(fs: float = 4096.0) -> pd.DataFrame:
    t = np.arange(0.0, 0.18, 1.0 / fs)
    velocity = np.full_like(t, 0.10)
    velocity[(t >= 0.015) & (t <= 0.055)] = 0.524
    velocity[(t >= 0.065) & (t <= 0.105)] = 0.35
    velocity[(t >= 0.115) & (t <= 0.155)] = -1.048
    displacement = np.cumsum(velocity) / fs * 1000.0

    current = np.full_like(t, 1.6)
    for at, start, end in (
        (0.03, 1.6, 0.3),
        (0.08, 0.3, 0.9),
        (0.13, 0.9, 1.6),
    ):
        ramp = (t >= at) & (t <= at + 0.001)
        current[ramp] = start + (end - start) * (t[ramp] - at) / 0.001
        current[t > at + 0.001] = end

    force = np.full_like(t, 7000.0)
    tau = 0.004
    mask = (t >= 0.0301) & (t < 0.0801)
    force[mask] = 4000.0 + 3000.0 * np.exp(-(t[mask] - 0.0301) / tau)
    mask = (t >= 0.0801) & (t < 0.115)
    force[mask] = 5500.0 - 1500.0 * np.exp(-(t[mask] - 0.0801) / tau)
    force[t >= 0.115] = -5500.0
    mask = t >= 0.1301
    force[mask] = -7000.0 + 1500.0 * np.exp(-(t[mask] - 0.1301) / tau)

    return pd.DataFrame(
        {TIME: t, DISP: displacement, LOAD: force, CURRENT: current}
    )


def test_target_speed_filter_excludes_off_target_current_step():
    result = analyze_response_time_v074(
        _dataset(_three_speed_events()),
        ResponseConfig(standard=ResponseStandard.BMW),
    )

    assert result.settings["Detected Current Events"] == 3
    assert result.settings["Accepted Target-Speed Events"] == 2
    assert result.settings["Rejected Non-target Events"] == 1
    assert result.events["Target Velocity m/s"].tolist() == pytest.approx(
        [0.524, -1.048],
        abs=1e-6,
    )
    assert result.events["Direction"].tolist() == ["Rebound", "Compression"]
    assert (result.events["Switch Time t90 ms"] > 0).all()


def test_target_speed_window_bridges_short_velocity_feedback_ripple():
    t = np.arange(0.0, 0.030, 1.0 / 4096.0)
    velocity = np.full_like(t, 0.131)
    velocity[(t >= 0.012) & (t <= 0.016)] = 0.148
    segment = pd.DataFrame({TIME: t, VELOCITY: velocity})

    component = _target_speed_component(
        segment,
        t0=0.010,
        signed_target_mps=0.131,
        tolerance_mps=0.0131,
    )

    assert component is not None
    left, right = component
    assert t[left] <= 0.001
    assert t[right] >= 0.028

    velocity[(t >= 0.012) & (t <= 0.024)] = 0.148
    sustained_segment = pd.DataFrame({TIME: t, VELOCITY: velocity})
    sustained_component = _target_speed_component(
        sustained_segment,
        t0=0.010,
        signed_target_mps=0.131,
        tolerance_mps=0.0131,
    )
    assert sustained_component is not None
    assert t[sustained_component[1]] < 0.014


def test_edge_event_boundaries_extrapolate_neighbor_half_spacing():
    assert _event_boundaries(1000, [200, 400, 600]) == [
        (100, 300),
        (300, 500),
        (500, 700),
    ]


def _full_bmw_sequence(fs: float = 4096.0) -> tuple[pd.DataFrame, list[tuple[str, str, str]]]:
    specs = [
        ("Soft", "Hard", "Rebound"),
        ("Soft", "Hard", "Compression"),
        ("Soft", "Medium", "Rebound"),
        ("Soft", "Medium", "Compression"),
        ("Hard", "Medium", "Rebound"),
        ("Hard", "Medium", "Compression"),
        ("Hard", "Soft", "Rebound"),
        ("Hard", "Soft", "Compression"),
    ]
    current_levels = {"Soft": 0.3, "Medium": 0.9, "Hard": 1.6}
    force_levels = {"Soft": 4000.0, "Medium": 5500.0, "Hard": 7000.0}
    accepted_times = [0.04 + 0.05 * index for index in range(len(specs))]
    t = np.arange(0.0, accepted_times[-1] + 0.04, 1.0 / fs)

    current_events: list[tuple[float, float, float]] = []
    for index, ((start_state, end_state, _direction), at) in enumerate(
        zip(specs, accepted_times)
    ):
        current_events.append(
            (at, current_levels[start_state], current_levels[end_state])
        )
        if index + 1 < len(specs):
            next_start = current_levels[specs[index + 1][0]]
            if abs(current_levels[end_state] - next_start) > 1e-12:
                current_events.append(
                    (at + 0.025, current_levels[end_state], next_start)
                )

    current = np.full_like(t, current_levels[specs[0][0]])
    for at, start, end in sorted(current_events):
        ramp = (t >= at) & (t <= at + 0.001)
        current[ramp] = start + (end - start) * (t[ramp] - at) / 0.001
        current[t > at + 0.001] = end

    velocity = np.full_like(t, 0.20)
    force = np.full_like(t, force_levels[specs[0][0]])
    tau = 0.004
    for index, ((start_state, end_state, direction), at) in enumerate(
        zip(specs, accepted_times)
    ):
        sign = 1.0 if direction == "Rebound" else -1.0
        target_window = (t >= at - 0.015) & (t <= at + 0.018)
        velocity[target_window] = sign * 0.524

        before = (t >= at - 0.015) & (t < at + 0.0001)
        force[before] = sign * force_levels[start_state]
        after = (t >= at + 0.0001) & (t <= at + 0.018)
        force[after] = (
            sign * force_levels[end_state]
            + (sign * force_levels[start_state] - sign * force_levels[end_state])
            * np.exp(-(t[after] - (at + 0.0001)) / tau)
        )

        if index + 1 < len(specs):
            next_at = accepted_times[index + 1]
            next_start, _next_end, next_direction = specs[index + 1]
            next_sign = 1.0 if next_direction == "Rebound" else -1.0
            between = (t > at + 0.018) & (t < next_at - 0.015)
            force[between] = next_sign * force_levels[next_start]

    displacement = np.cumsum(velocity) / fs * 1000.0
    return (
        pd.DataFrame(
            {TIME: t, DISP: displacement, LOAD: force, CURRENT: current}
        ),
        specs,
    )


def test_full_bmw_file_returns_four_stages_times_two_directions():
    frame, specs = _full_bmw_sequence()
    result = analyze_response_time_v074(
        _dataset(frame, "bmw_full_sequence.dat"),
        ResponseConfig(standard=ResponseStandard.BMW),
    )

    assert result.settings["Accepted Target-Speed Events"] == 8
    assert result.settings["Rejected Non-target Events"] == 7
    assert result.events["Stage"].tolist() == [
        f"{start}→{end}" for start, end, _direction in specs
    ]
    assert result.events["Direction"].tolist() == [
        direction for _start, _end, direction in specs
    ]
    assert np.allclose(
        np.abs(result.events["Target Velocity m/s"].to_numpy(float)),
        0.524,
    )
