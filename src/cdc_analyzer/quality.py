from __future__ import annotations

import numpy as np
import pandas as pd

from .analysis import CURRENT, DISP, LOAD, TIME

REQUIRED_NUMERIC_CHANNELS = [TIME, DISP, LOAD, CURRENT]


def _safe_float(value: float | int | np.floating) -> float:
    return float(value) if np.isfinite(value) else float("nan")


def build_block_quality(frame: pd.DataFrame) -> pd.DataFrame:
    """Build traceable data-quality diagnostics for each imported acquisition block.

    Only objective/raw-data checks are promoted to Warning/Invalid. Metrics such as
    sampling frequency and displacement step are reported for engineering review but
    are not judged against a customer limit unless the data itself is structurally
    invalid.
    """
    rows: list[dict[str, object]] = []
    if frame.empty:
        return pd.DataFrame(columns=["Block ID", "Status", "Issues"])

    for block_id, block in frame.groupby("Block ID", sort=False):
        issues: list[str] = []
        status = "OK"
        count = int(len(block))
        numeric = block[REQUIRED_NUMERIC_CHANNELS].apply(pd.to_numeric, errors="coerce")
        finite_mask = np.isfinite(numeric.to_numpy(float)).all(axis=1)
        finite_count = int(finite_mask.sum())

        if count < 5:
            issues.append("too few samples")
            status = "Invalid"
        if finite_count != count:
            issues.append(f"non-finite samples: {count - finite_count}")
            status = "Invalid"

        valid = numeric.loc[finite_mask]
        t = valid[TIME].to_numpy(float)
        x = valid[DISP].to_numpy(float)
        load = valid[LOAD].to_numpy(float)
        current = valid[CURRENT].to_numpy(float)

        if len(t) >= 2:
            dt = np.diff(t)
            non_increasing = int(np.sum(dt <= 0))
            if non_increasing:
                issues.append(f"non-increasing time intervals: {non_increasing}")
                status = "Invalid"
            positive_dt = dt[dt > 0]
            median_dt = float(np.median(positive_dt)) if len(positive_dt) else float("nan")
            sample_rate = 1.0 / median_dt if np.isfinite(median_dt) and median_dt > 0 else float("nan")
            max_dt = float(np.max(positive_dt)) if len(positive_dt) else float("nan")
            gap_ratio = max_dt / median_dt if np.isfinite(max_dt) and np.isfinite(median_dt) and median_dt > 0 else float("nan")
            if np.isfinite(gap_ratio) and gap_ratio > 3.0 and status != "Invalid":
                issues.append(f"large time gap ratio: {gap_ratio:.2f}")
                status = "Warning"
        else:
            median_dt = sample_rate = max_dt = gap_ratio = float("nan")

        if len(x) >= 2:
            dx = np.abs(np.diff(x))
            median_abs_dx = float(np.median(dx))
            max_abs_dx = float(np.max(dx))
        else:
            median_abs_dx = max_abs_dx = float("nan")

        rows.append({
            "Block ID": int(block_id),
            "Sample Count": count,
            "Finite Sample Count": finite_count,
            "Start Time s": _safe_float(t[0]) if len(t) else float("nan"),
            "End Time s": _safe_float(t[-1]) if len(t) else float("nan"),
            "Median dt s": _safe_float(median_dt),
            "Sample Rate Hz": _safe_float(sample_rate),
            "Max dt s": _safe_float(max_dt),
            "Max/Median dt": _safe_float(gap_ratio),
            "Displacement Min mm": _safe_float(np.min(x)) if len(x) else float("nan"),
            "Displacement Max mm": _safe_float(np.max(x)) if len(x) else float("nan"),
            "Displacement Span mm": _safe_float(np.ptp(x)) if len(x) else float("nan"),
            "Median |dX| mm": _safe_float(median_abs_dx),
            "Max |dX| mm": _safe_float(max_abs_dx),
            "Load Min N": _safe_float(np.min(load)) if len(load) else float("nan"),
            "Load Max N": _safe_float(np.max(load)) if len(load) else float("nan"),
            "Current Median A": _safe_float(np.median(current)) if len(current) else float("nan"),
            "Current Std A": _safe_float(np.std(current, ddof=0)) if len(current) else float("nan"),
            "Status": status,
            "Issues": "; ".join(issues),
        })
    return pd.DataFrame(rows)


def overall_quality_status(quality: pd.DataFrame) -> str:
    if quality.empty:
        return "Invalid"
    statuses = set(quality["Status"].astype(str))
    if "Invalid" in statuses:
        return "Invalid"
    if "Warning" in statuses:
        return "Warning"
    return "OK"
