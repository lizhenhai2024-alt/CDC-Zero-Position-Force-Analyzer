from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import pandas as pd

REQUIRED_COLUMNS = [
    "Running Time",
    "Axial Displacement",
    "Axial Load",
    "CDC 1 Current FB_1",
]

COLUMN_ALIASES = {
    "Running Time": {"running time", "time", "running_time"},
    "Axial Displacement": {"axial displacement", "displacement", "stroke", "axial_displacement"},
    "Axial Load": {"axial load", "load", "force", "axial_load"},
    "CDC 1 Current FB_1": {
        "cdc 1 current fb_1",
        "cdc1 current fb_1",
        "cdc current",
        "current",
        "current fb",
        "current feedback",
    },
}


@dataclass(slots=True)
class DataSet:
    data: pd.DataFrame
    source_path: Path
    source_format: str
    metadata: dict[str, object] = field(default_factory=dict)


def _normalize_name(name: object) -> str:
    return " ".join(str(name).strip().lower().replace("_", " ").split())


def _canonicalize_columns(columns: Iterable[object]) -> dict[object, str]:
    mapping: dict[object, str] = {}
    normalized_aliases = {
        canonical: {_normalize_name(v) for v in aliases | {canonical}}
        for canonical, aliases in COLUMN_ALIASES.items()
    }
    for col in columns:
        key = _normalize_name(col)
        for canonical, aliases in normalized_aliases.items():
            if key in aliases:
                mapping[col] = canonical
                break
    return mapping


def _coerce_required_numeric(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    out = df.copy()
    for col in REQUIRED_COLUMNS:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=REQUIRED_COLUMNS).reset_index(drop=True)
    if out.empty:
        raise ValueError("No valid numeric test data rows found")
    return out


def _parse_mts_dat(path: Path) -> DataSet:
    # MTS text exports may repeat Data Acquisition blocks, headers, and unit rows.
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    rows: list[list[float | int]] = []
    block_id = 0
    block_metadata: list[dict[str, object]] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.startswith("Data Acquisition"):
            i += 1
            continue

        block_id += 1
        block_metadata.append({"Block ID": block_id, "header": line.strip()})
        if i + 2 >= len(lines):
            break

        header = [v.strip() for v in lines[i + 1].split("\t") if v.strip()]
        # Allow tabs used for layout; locate the required header row by names.
        if not all(c in header for c in REQUIRED_COLUMNS):
            i += 1
            continue

        j = i + 3  # skip units row
        while j < len(lines) and not lines[j].startswith("Data Acquisition"):
            raw = lines[j].strip()
            if raw:
                parts = [p.strip() for p in lines[j].split("\t")]
                if len(parts) >= 4:
                    try:
                        vals = [float(parts[k]) for k in range(4)]
                    except (TypeError, ValueError):
                        pass
                    else:
                        rows.append([*vals, block_id])
            j += 1
        i = j

    if not rows:
        raise ValueError("No MTS Data Acquisition blocks with valid rows were found")

    df = pd.DataFrame(rows, columns=[*REQUIRED_COLUMNS, "Block ID"])
    df["Source Row"] = range(1, len(df) + 1)
    return DataSet(
        data=df,
        source_path=path,
        source_format="mts_dat",
        metadata={"block_count": block_id, "blocks": block_metadata},
    )


def _read_tabular(path: Path) -> DataSet:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(path)
        fmt = "csv"
    elif suffix in {".xlsx", ".xlsm"}:
        df = pd.read_excel(path)
        fmt = "xlsx"
    else:
        raise ValueError(f"Unsupported tabular format: {suffix}")

    df = df.rename(columns=_canonicalize_columns(df.columns))
    df = _coerce_required_numeric(df)
    if "Block ID" not in df.columns:
        df["Block ID"] = 1
    df["Source Row"] = range(1, len(df) + 1)
    return DataSet(data=df, source_path=path, source_format=fmt, metadata={"block_count": int(df["Block ID"].nunique())})


def load_test_data(path: str | Path) -> DataSet:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    if suffix == ".dat":
        return _parse_mts_dat(path)
    if suffix in {".csv", ".xlsx", ".xlsm"}:
        return _read_tabular(path)
    raise ValueError(f"Unsupported file type: {suffix}")
