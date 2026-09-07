from __future__ import annotations

import numpy as np
import pandas as pd


SWEEP_COLUMNS = [
    "Current Label A",
    "Up Rebound N",
    "Down Rebound N",
    "Delta Rebound N",
    "Up Compression N",
    "Down Compression N",
    "Delta Compression N",
    "Up Run Count",
    "Down Run Count",
    "Coverage",
]


def build_sweep_comparison(runs: pd.DataFrame) -> pd.DataFrame:
    """Compare the selected result from increasing- and decreasing-current runs.

    Delta is defined as Down - Up.  The table is descriptive only: it deliberately
    does not turn sweep hysteresis into a pass/fail decision without an explicit
    engineering or customer limit.
    """
    required = {"Current Label A", "Sweep Direction", "Rebound N", "Compression N"}
    if runs.empty or not required.issubset(runs.columns):
        return pd.DataFrame(columns=SWEEP_COLUMNS)

    valid = runs.copy()
    valid = valid[valid["Sweep Direction"].isin(["Up", "Down"])]
    valid = valid.dropna(subset=["Current Label A", "Rebound N", "Compression N"])
    if valid.empty:
        return pd.DataFrame(columns=SWEEP_COLUMNS)

    grouped = valid.groupby(["Current Label A", "Sweep Direction"], as_index=False).agg(
        **{
            "Rebound N": ("Rebound N", "mean"),
            "Compression N": ("Compression N", "mean"),
            "Run Count": ("Run ID", "count") if "Run ID" in valid.columns else ("Rebound N", "count"),
        }
    )

    rows: list[dict[str, object]] = []
    for current, current_rows in grouped.groupby("Current Label A", sort=True):
        by_direction = current_rows.set_index("Sweep Direction")
        up = by_direction.loc["Up"] if "Up" in by_direction.index else None
        down = by_direction.loc["Down"] if "Down" in by_direction.index else None

        up_r = float(up["Rebound N"]) if up is not None else np.nan
        down_r = float(down["Rebound N"]) if down is not None else np.nan
        up_c = float(up["Compression N"]) if up is not None else np.nan
        down_c = float(down["Compression N"]) if down is not None else np.nan
        up_count = int(up["Run Count"]) if up is not None else 0
        down_count = int(down["Run Count"]) if down is not None else 0

        rows.append(
            {
                "Current Label A": float(current),
                "Up Rebound N": up_r,
                "Down Rebound N": down_r,
                "Delta Rebound N": down_r - up_r if np.isfinite(up_r) and np.isfinite(down_r) else np.nan,
                "Up Compression N": up_c,
                "Down Compression N": down_c,
                "Delta Compression N": down_c - up_c if np.isfinite(up_c) and np.isfinite(down_c) else np.nan,
                "Up Run Count": up_count,
                "Down Run Count": down_count,
                "Coverage": "Up + Down" if up_count and down_count else "Up only" if up_count else "Down only",
            }
        )
    return pd.DataFrame(rows, columns=SWEEP_COLUMNS)
