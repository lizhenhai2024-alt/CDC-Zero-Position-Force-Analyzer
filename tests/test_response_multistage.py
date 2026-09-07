from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from cdc_analyzer.dynamic_analysis import CURRENT, DISP, LOAD, TIME, ResponseConfig, ResponseStandard
from cdc_analyzer.parser import DataSet
from cdc_analyzer.response_multistage import analyze_response_time_multistage


STATE_CURRENT = {"Soft": 0.3, "Medium": 0.8, "Hard": 1.6}
STATE_FORCE = {"Soft": 500.0, "Medium": 1050.0, "Hard": 1850.0}


def _response_block(block_id: int, start_state: str, end_state: str, direction: str) -> pd.DataFrame:
    fs = 4096.0
    local_t = np.arange(0.0, 0.050, 1.0 / fs)
    start_i = STATE_CURRENT[start_state]
    end_i = STATE_CURRENT[end_state]
    step_start = 0.015
    step_end = 0.016

    current = np.full_like(local_t, start_i)
    ramp = (local_t >= step_start) & (local_t <= step_end)
    current[local_t > step_end] = end_i
    current[ramp] = start_i + (end_i - start_i) * (local_t[ramp] - step_start) / (step_end - step_start)

    sign = 1.0 if direction == "Rebound" else -1.0
    start_f = sign * STATE_FORCE[start_state]
    end_f = sign * STATE_FORCE[end_state]
    response_start = step_start + 0.0007
    tau = 0.0035
    force = np.full_like(local_t, start_f)
    after = local_t >= response_start
    force[after] = end_f + (start_f - end_f) * np.exp(-(local_t[after] - response_start) / tau)

    speed_m_s = 0.524
    displacement = sign * speed_m_s * 1000.0 * (local_t - local_t.mean())
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


def test_bmw_full_file_detects_four_stages_in_rebound_and_compression(tmp_path: Path):
    stages = (
        ("Soft", "Hard"),
        ("Soft", "Medium"),
        ("Hard", "Medium"),
        ("Hard", "Soft"),
    )
    blocks = []
    block_id = 1
    for start_state, end_state in stages:
        for direction in ("Rebound", "Compression"):
            blocks.append(_response_block(block_id, start_state, end_state, direction))
            block_id += 1

    dataset = DataSet(
        pd.concat(blocks, ignore_index=True),
        tmp_path / "bmw_full_response.dat",
        "synthetic",
    )
    result = analyze_response_time_multistage(
        dataset,
        ResponseConfig(
            standard=ResponseStandard.BMW,
            trigger_fraction=0.10,
            end_average_fraction=0.02,
        ),
    )

    assert len(result.events) == 8
    assert set(result.events["Direction"]) == {"Rebound", "Compression"}
    assert set(result.events["Stage"]) == {
        "Soft → Hard",
        "Soft → Medium",
        "Hard → Medium",
        "Hard → Soft",
    }
    counts = result.events.groupby(["Stage", "Direction"]).size()
    assert (counts == 1).all()
    assert np.isfinite(result.events["F10 N"]).all()
    assert np.isfinite(result.events["Switch Time t10 ms"]).all()
    assert np.isfinite(result.events["Switch Time t63 ms"]).all()
    assert np.isfinite(result.events["Switch Time t90 ms"]).all()
    assert np.allclose(np.abs(result.events["Target Velocity m/s"]), 0.524, atol=1e-9)
