from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from cdc_analyzer.dynamic_analysis import CURRENT, DISP, LOAD, TIME, ResponseConfig, ResponseStandard
from cdc_analyzer.parser import DataSet
from cdc_analyzer.response_target_velocity_v074 import analyze_response_time_target_velocity


def _block(block_id: int, speed_m_s: float, start_i: float = 0.3, end_i: float = 1.6) -> pd.DataFrame:
    fs = 4096.0
    local_t = np.arange(0.0, 0.050, 1.0 / fs)
    step_start = 0.015
    step_end = 0.016

    current = np.full_like(local_t, start_i)
    ramp = (local_t >= step_start) & (local_t <= step_end)
    current[local_t > step_end] = end_i
    current[ramp] = start_i + (end_i - start_i) * (local_t[ramp] - step_start) / (step_end - step_start)

    start_f = 600.0
    end_f = 1900.0
    response_start = step_start + 0.0007
    tau = 0.0035
    force = np.full_like(local_t, start_f)
    after = local_t >= response_start
    force[after] = end_f + (start_f - end_f) * np.exp(-(local_t[after] - response_start) / tau)

    displacement = speed_m_s * 1000.0 * (local_t - local_t.mean())
    absolute_t = local_t + block_id * 0.10
    return pd.DataFrame(
        {
            TIME: absolute_t,
            DISP: displacement,
            LOAD: force,
            CURRENT: current,
            "Block ID": block_id,
        }
    )


def test_v074_keeps_only_bmw_events_near_target_speed(tmp_path: Path):
    data = pd.concat(
        [
            _block(1, 0.524),
            _block(2, 0.35),  # not close to 0.0131 / 0.524 / 1.048 m/s
            _block(3, 1.048),
        ],
        ignore_index=True,
    )
    dataset = DataSet(data, tmp_path / "response.dat", "synthetic")
    result = analyze_response_time_target_velocity(
        dataset,
        ResponseConfig(standard=ResponseStandard.BMW, trigger_fraction=0.10, end_average_fraction=0.02),
    )

    assert len(result.events) == 2
    assert result.settings["Detected Raw Events"] == 3
    assert result.settings["Accepted Target-Speed Events"] == 2
    assert result.settings["Rejected Non-target Events"] == 1
    assert np.allclose(
        np.sort(np.abs(result.events["Target Velocity m/s"].to_numpy(float))),
        np.asarray([0.524, 1.048]),
        atol=1e-9,
    )
    assert np.all(result.events["Target Velocity Deviation %"].to_numpy(float) < 1.0)
    assert np.isfinite(result.events["Switch Time t90 ms"]).all()


def test_v074_raises_when_no_current_step_occurs_near_target_speed(tmp_path: Path):
    dataset = DataSet(_block(1, 0.35), tmp_path / "off_target.dat", "synthetic")
    with pytest.raises(ValueError, match="No valid response event near OEM target speed"):
        analyze_response_time_target_velocity(
            dataset,
            ResponseConfig(standard=ResponseStandard.BMW),
        )


def test_v074_grid_uses_one_major_tick_level():
    from cdc_analyzer.gui_release_v074 import _major_tick_levels

    assert _major_tick_levels(0.5) == [(0.5, 0.0)]
    assert _major_tick_levels(1000.0) == [(1000.0, 0.0)]
