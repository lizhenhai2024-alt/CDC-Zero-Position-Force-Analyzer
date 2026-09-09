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
    HysteresisConfig,
    HysteresisStandard,
    ResponseConfig,
    ResponseStandard,
    analyze_hysteresis,
    analyze_response_time,
    load_dynamic_test_data,
)
from cdc_analyzer.parser import DataSet, load_test_data


def test_mts_parser_respects_reordered_channel_headers(tmp_path: Path):
    path = tmp_path / "reordered.dat"
    path.write_text(
        "MTS793|MPT|ENU|1\n\n"
        "Data Acquisition\tTime:\t1.0\ts\n"
        "Running Time\tCDC 1 Current FB_1\tAxial Displacement\tAxial Load\n"
        "s\tA\tmm\tN\n"
        "0.00\t0.30\t10.0\t-100.0\n"
        "0.01\t0.40\t11.0\t-110.0\n",
        encoding="utf-8",
    )
    dataset = load_test_data(path)
    assert dataset.data[TIME].tolist() == pytest.approx([0.0, 0.01])
    assert dataset.data[CURRENT].tolist() == pytest.approx([0.3, 0.4])
    assert dataset.data[DISP].tolist() == pytest.approx([10.0, 11.0])
    assert dataset.data[LOAD].tolist() == pytest.approx([-100.0, -110.0])


def test_headerless_response_channel_inference(tmp_path: Path):
    path = tmp_path / "response.dat"
    t = np.arange(0.0, 0.03, 1 / 4096.0)
    load = 7000 - 2500 / (1 + np.exp(-(t - 0.015) / 0.001))
    current = 1.6 - 1.3 / (1 + np.exp(-(t - 0.010) / 0.0005))
    displacement = 12.0 + 1000.0 * t
    lines = [f"{a}\t{b}\t{c}\t{d}\tmanual" for a, b, c, d in zip(t, load, current, displacement)]
    path.write_text("\n".join(lines), encoding="utf-8")

    dataset = load_dynamic_test_data(path)
    mapping = dataset.metadata["inferred_mapping"]
    assert dataset.source_format == "headerless_numeric_dat"
    assert mapping["time_column_1based"] == 1
    assert mapping["load_column_1based"] == 2
    assert mapping["current_column_1based"] == 3
    assert mapping["displacement_column_1based"] == 4
    assert len(dataset.data) == len(t)


def test_response_time_interpolates_63_and_90_percent(tmp_path: Path):
    fs = 4096.0
    t = np.arange(0.0, 0.05, 1 / fs)
    trigger_time = 0.0101
    current = np.full_like(t, 1.6)
    ramp = (t >= 0.0100) & (t <= 0.0110)
    current[t > 0.0110] = 0.3
    current[ramp] = 1.6 + (0.3 - 1.6) * (t[ramp] - 0.0100) / 0.0010
    force = np.full_like(t, 7000.0)
    tau = 0.004
    after = t >= trigger_time
    force[after] = 4000.0 + 3000.0 * np.exp(-(t[after] - trigger_time) / tau)
    displacement = 1000.0 * t
    frame = pd.DataFrame({TIME: t, DISP: displacement, LOAD: force, CURRENT: current, "Block ID": 1})
    dataset = DataSet(frame, tmp_path / "synthetic.dat", "synthetic")

    result = analyze_response_time(
        dataset,
        ResponseConfig(standard=ResponseStandard.AUDI, trigger_fraction=0.10, end_average_fraction=0.02),
    )
    row = result.events.iloc[0]
    assert row["Sample Rate Hz"] == pytest.approx(fs, rel=0.01)
    assert row["Direction"] == "Rebound"
    assert row["Switch Time t63 ms"] == pytest.approx(4.0, abs=0.8)
    assert row["Switch Time t90 ms"] == pytest.approx(9.2, abs=1.0)
    assert row["Dead Time t1 ms"] > 0


def _bmw_block(block_id: int, current: float, rebound_force: float, compression_force: float) -> pd.DataFrame:
    t = np.linspace(0.0, 1.0, 401)
    x = -50.0 * np.cos(2.0 * np.pi * t)
    velocity = np.gradient(x, t)
    force = np.where(velocity >= 0, rebound_force, compression_force)
    return pd.DataFrame(
        {
            TIME: t + block_id * 2.0,
            DISP: x,
            LOAD: force,
            CURRENT: current,
            "Block ID": block_id,
        }
    )


def test_bmw_hysteresis_pairs_increasing_and_decreasing_current(tmp_path: Path):
    blocks = [
        _bmw_block(1, 0.3, 700, -1400),
        _bmw_block(2, 0.5, 1000, -1700),
        _bmw_block(3, 0.7, 1400, -2000),
        _bmw_block(4, 0.5, 1020, -1660),
        _bmw_block(5, 0.3, 710, -1380),
    ]
    dataset = DataSet(pd.concat(blocks, ignore_index=True), tmp_path / "bmw.dat", "synthetic")
    result = analyze_hysteresis(dataset, HysteresisConfig(standard=HysteresisStandard.BMW))

    r05 = result.summary[(result.summary["Current A"] == 0.5) & (result.summary["Direction"] == "Rebound")].iloc[0]
    c05 = result.summary[(result.summary["Current A"] == 0.5) & (result.summary["Direction"] == "Compression")].iloc[0]
    assert r05["Hysteresis N"] == pytest.approx(20.0, abs=0.5)
    assert r05["Hysteresis %"] == pytest.approx(20.0 / 1010.0 * 100.0, abs=0.1)
    assert c05["Hysteresis N"] == pytest.approx(40.0, abs=0.5)
    assert c05["Reference Damping Force N"] == pytest.approx(1680.0, abs=0.5)
    assert set(result.summary["Status"]) == {"Not evaluated"}


def _audi_plateau(block_id: int, current: float, magnitude: float, kfm_offset: float = 0.0) -> pd.DataFrame:
    cycles = 7
    points_per_cycle = 160
    local_t = np.linspace(0.0, cycles / 1.31, cycles * points_per_cycle + 1)
    x = -50.0 * np.cos(2.0 * np.pi * 1.31 * local_t)
    velocity = np.gradient(x, local_t)
    force = np.where(velocity >= 0, magnitude + kfm_offset, -(magnitude + kfm_offset))
    return pd.DataFrame(
        {
            TIME: local_t + block_id * 10.0,
            DISP: x,
            LOAD: force,
            CURRENT: current,
            "Block ID": block_id,
        }
    )


def test_audi_hysteresis_excludes_first_cycle_and_pairs_kfm_plateaus(tmp_path: Path):
    blocks = [
        _audi_plateau(1, 0.3, 500),
        _audi_plateau(2, 0.8, 1000),
        _audi_plateau(3, 1.6, 2000),
        _audi_plateau(4, 0.8, 1000, kfm_offset=20),
        _audi_plateau(5, 0.3, 500),
    ]
    dataset = DataSet(pd.concat(blocks, ignore_index=True), tmp_path / "audi.dat", "synthetic")
    config = HysteresisConfig(
        standard=HysteresisStandard.AUDI,
        audi_soft_current_a=0.3,
        audi_kfm_current_a=0.8,
        audi_hard_current_a=1.6,
    )
    result = analyze_hysteresis(dataset, config)

    assert (result.runs["Retained Cycle Count"] >= 4).all()
    rebound = result.summary[result.summary["Direction"] == "Rebound"].iloc[0]
    assert rebound["Excursion State"] == "Hard"
    assert rebound["Hysteresis N"] == pytest.approx(20.0, abs=2.0)
    assert rebound["Spread Fmax-Fmin N"] == pytest.approx(1500.0, abs=5.0)
    assert rebound["Hysteresis %"] == pytest.approx(20.0 / 1500.0 * 100.0, abs=0.2)
