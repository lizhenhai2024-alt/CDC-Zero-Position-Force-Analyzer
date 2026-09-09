from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from cdc_analyzer.dynamic_analysis import CURRENT, DISP, LOAD, TIME, ResponseConfig, ResponseStandard
from cdc_analyzer.parser import DataSet
from cdc_analyzer.response_v080 import (
    BMW_TARGET_SPEEDS_MPS,
    analyze_response_time_v080,
    parse_target_speeds,
)


def _response_dataset(speed_mps: float) -> DataSet:
    sample_rate = 4096.0
    t = np.arange(0.0, 0.10, 1.0 / sample_rate)
    displacement_mm = speed_mps * 1000.0 * t
    current = 0.30 + 1.30 / (1.0 + np.exp(-(t - 0.040) / 0.00045))
    load = 1200.0 + 1800.0 / (1.0 + np.exp(-(t - 0.045) / 0.0012))
    frame = pd.DataFrame(
        {
            TIME: t,
            DISP: displacement_mm,
            LOAD: load,
            CURRENT: current,
        }
    )
    return DataSet(
        data=frame,
        source_path=Path("synthetic_response.dat"),
        source_format="synthetic",
        metadata={},
    )


def test_bmw_default_response_speed_is_0131_not_00131():
    assert BMW_TARGET_SPEEDS_MPS == pytest.approx((0.131, 0.524, 1.048))
    result = analyze_response_time_v080(
        _response_dataset(0.131),
        ResponseConfig(standard=ResponseStandard.BMW),
    )
    assert not result.events.empty
    assert float(result.events.iloc[0]["Target Velocity m/s"]) == pytest.approx(0.131)


def test_custom_customer_target_speed_is_not_locked_to_oem_profile():
    result = analyze_response_time_v080(
        _response_dataset(0.300),
        ResponseConfig(standard=ResponseStandard.BMW),
        target_speeds_mps=(0.1, 0.3, 0.6, 1.0),
    )
    assert not result.events.empty
    assert float(result.events.iloc[0]["Target Velocity m/s"]) == pytest.approx(0.3)
    assert result.settings["Target Speeds m/s"] == "0.1, 0.3, 0.6, 1"

    row = result.events.iloc[0]
    i10_time = float(row["I10 Crossing Time s"])
    assert float(row["Dead Time t1 ms"]) == pytest.approx(
        (float(row["F1 Crossing Time s"]) - i10_time) * 1000.0
    )
    assert float(row["Switch Time t63 ms"]) == pytest.approx(
        (float(row["F63 Crossing Time s"]) - i10_time) * 1000.0
    )
    assert float(row["Switch Time t90 ms"]) == pytest.approx(
        (float(row["F90 Crossing Time s"]) - i10_time) * 1000.0
    )
    assert row["Timing Reference"] == "I10% current crossing"
    assert result.settings["Timing Reference"] == (
        "Force-threshold crossing time minus I10% current crossing time"
    )


@pytest.mark.parametrize("force_scale", (1.0, -1.0))
def test_force_thresholds_keep_f90_before_f100_in_response_direction(force_scale):
    """F90 stays between F63 and the F100 endpoint for either force sign."""
    dataset = _response_dataset(0.300)
    dataset.data[LOAD] *= force_scale
    result = analyze_response_time_v080(
        dataset,
        ResponseConfig(standard=ResponseStandard.BMW),
        target_speeds_mps=(0.3,),
    )
    row = result.events.iloc[0]
    direction = float(row["Delta F N"])
    f1, f63, f90, f100 = (float(row[key]) for key in ("F1 N", "F63 N", "F90 N", "F100 N"))

    assert (f63 - f1) * direction > 0
    assert (f90 - f63) * direction > 0
    assert (f100 - f90) * direction > 0
    assert abs(f100 - f90) < abs(f100 - f63)


def test_target_speed_parser_accepts_customer_lists():
    assert parse_target_speeds("0.1, 0.3; 0.6 1.0") == pytest.approx((0.1, 0.3, 0.6, 1.0))
    with pytest.raises(ValueError):
        parse_target_speeds("0.3, 0")


def test_v080_gui_exposes_editable_target_speed_list():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6 import QtWidgets
    from cdc_analyzer.gui_release_v080 import _build_release_gui_classes_v080

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    MainWindow = _build_release_gui_classes_v080()
    window = MainWindow()
    pages = window.dynamic_pages

    assert pages.response_target_speeds.isVisibleTo(pages.response_page)
    assert pages.response_target_speeds.text() == "0.131, 0.524, 1.048"
    pages.response_target_speeds.setText("0.1, 0.3, 0.6, 1.0")
    assert parse_target_speeds(pages.response_target_speeds.text()) == pytest.approx((0.1, 0.3, 0.6, 1.0))

    window.close()
    app.processEvents()
