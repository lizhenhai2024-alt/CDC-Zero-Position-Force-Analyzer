from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cdc_analyzer.analysis import AnalyzerConfig, CDCAnalyzer, EvaluationProfile
from cdc_analyzer.dynamic_analysis import HysteresisConfig, HysteresisStandard, ResponseConfig, ResponseStandard, analyze_hysteresis, load_dynamic_test_data
from cdc_analyzer.parser import load_test_data
from cdc_analyzer.response_v080 import analyze_response_time_v080
from verify_golden_evidence import _algorithm_state, _expected_digest, verify


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _source(case: dict[str, Any], path: Path) -> None:
    if not path.is_file():
        raise AssertionError(f"{case['id']}: private source missing: {path}")
    if path.stat().st_size != int(case["source_size_bytes"]):
        raise AssertionError(f"{case['id']}: source size mismatch")
    if _sha256(path) != case["source_sha256"]:
        raise AssertionError(f"{case['id']}: source SHA-256 mismatch")


def _close(actual: float, expected: float, tol: float, label: str) -> None:
    if not math.isfinite(float(actual)) or not math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=float(tol)):
        raise AssertionError(f"{label}: {actual!r} != {expected!r} (abs_tol={tol})")


def _audi(case: dict[str, Any], path: Path) -> dict[str, Any]:
    result = CDCAnalyzer(AnalyzerConfig(profile=EvaluationProfile.AUDI)).analyze(load_test_data(path))
    exp, tol = case["expected"], float(case["tolerance"]["force_n_abs"])
    if len(result.runs) != int(exp["run_count"]) or len(result.cycles) != int(exp["complete_cycle_count"]):
        raise AssertionError(f"{case['id']}: run/cycle count mismatch")
    actual = {round(float(r["Current Label A"]), 1): r for _, r in result.summary.iterrows()}
    for approved in exp["summary"]:
        cur = round(float(approved["current_a"]), 1)
        row = actual.get(cur)
        if row is None:
            raise AssertionError(f"{case['id']}: missing {cur:.1f} A")
        _close(row["Rebound N"], approved["rebound_n"], tol, f"{case['id']} {cur:.1f}A rebound")
        _close(row["Compression N"], approved["compression_n"], tol, f"{case['id']} {cur:.1f}A compression")
        if int(row["Run Count"]) != int(approved["run_count"]):
            raise AssertionError(f"{case['id']} {cur:.1f}A run count mismatch")
    return {"run_count": len(result.runs), "complete_cycle_count": len(result.cycles), "summary_current_count": len(result.summary), "all_status_ok": bool((result.runs["Status"] == "OK").all())}


def _hysteresis(case: dict[str, Any], path: Path) -> dict[str, Any]:
    ds = load_dynamic_test_data(path)
    result = analyze_hysteresis(ds, HysteresisConfig(standard=HysteresisStandard.BMW, zero_target_mm=float(case["expected"]["zero_target_mm"])))
    ftol = float(case["tolerance"]["force_n_abs"])
    ptol = float(case["tolerance"]["hysteresis_percent_abs"])
    actual = {(round(float(r["Current A"]), 1), str(r["Direction"])): r for _, r in result.summary.iterrows()}
    for approved in case["expected"]["paired_summary"]:
        key = (round(float(approved["current_a"]), 1), str(approved["direction"]))
        row = actual.get(key)
        if row is None:
            raise AssertionError(f"{case['id']}: missing paired summary {key}")
        for col, k in (("Up Force N", "up_force_n"), ("Down Force N", "down_force_n"), ("Reference Damping Force N", "reference_force_n"), ("Hysteresis N", "hysteresis_n")):
            _close(row[col], approved[k], ftol, f"{case['id']} {key} {col}")
        _close(row["Hysteresis %"], approved["hysteresis_percent"], ptol, f"{case['id']} {key} Hysteresis %")
    return {"block_count": int((ds.metadata or {}).get("block_count", 0)), "run_row_count": len(result.runs), "paired_summary_count": len(result.summary), "max_hysteresis_percent": float(result.summary["Hysteresis %"].max())}


def _response(case: dict[str, Any], path: Path) -> dict[str, Any]:
    exp, tol = case["expected"], case["tolerance"]
    result = analyze_response_time_v080(load_dynamic_test_data(path), ResponseConfig(standard=ResponseStandard.BMW), target_speeds_mps=exp["target_speeds_mps"])
    if len(result.events) != int(exp["event_count"]):
        raise AssertionError(f"{case['id']}: event count mismatch")
    row = result.events.iloc[0]
    for col, key, at in (
        ("Target Velocity m/s", "target_velocity_mps", 1e-12),
        ("Sample Rate Hz", "sample_rate_hz", tol["sample_rate_hz_abs"]),
        ("Current Start A", "current_start_a", tol["current_a_abs"]),
        ("Current End A", "current_end_a", tol["current_a_abs"]),
        ("Trigger Current A", "trigger_current_a", tol["current_a_abs"]),
        ("I10 Crossing Time s", "i10_crossing_time_s", tol["time_s_abs"]),
        ("F0 N", "f0_n", tol["force_n_abs"]),
        ("F100 N", "f100_n", tol["force_n_abs"]),
        ("Dead Time t1 ms", "dead_time_t1_ms", tol["time_ms_abs"]),
        ("Switch Time t63 ms", "switch_time_t63_ms", tol["time_ms_abs"]),
        ("Switch Time t90 ms", "switch_time_t90_ms", tol["time_ms_abs"]),
    ):
        _close(row[col], exp[key], at, f"{case['id']} {col}")
    identity = (float(row["F90 Crossing Time s"]) - float(row["I10 Crossing Time s"])) * 1000.0
    _close(identity, row["Switch Time t90 ms"], tol["time_ms_abs"], f"{case['id']} t90 identity")
    if str(row["Timing Reference"]) != exp["timing_reference"]:
        raise AssertionError(f"{case['id']}: timing reference mismatch")
    return {"event_count": len(result.events), "target_velocity_mps": float(row["Target Velocity m/s"]), "switch_time_t90_ms": float(row["Switch Time t90 ms"]), "sample_rate_hz": float(row["Sample Rate Hz"]), "timing_identity_error_ms": float(identity - row["Switch Time t90 ms"])}


def _head(root: Path) -> str:
    p = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, encoding="utf-8", check=False)
    return p.stdout.strip() if p.returncode == 0 else "unknown"


def main() -> int:
    p = argparse.ArgumentParser(description="Run private real-bench Golden regression and refresh hash-only evidence.")
    p.add_argument("--audi", required=True, type=Path)
    p.add_argument("--bmw-hysteresis", required=True, type=Path)
    p.add_argument("--bmw-response", required=True, type=Path)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest_path = root / "golden" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = {c["id"]: c for c in manifest["cases"]}
    sources = {"REAL-AUDI-CENTER-001": a.audi, "REAL-BMW-HYST-001": a.bmw_hysteresis, "REAL-BMW-RESPONSE-1048-001": a.bmw_response}
    runners = {"REAL-AUDI-CENTER-001": _audi, "REAL-BMW-HYST-001": _hysteresis, "REAL-BMW-RESPONSE-1048-001": _response}
    evidence_cases = []
    for case_id, path in sources.items():
        case = cases[case_id]
        _source(case, path)
        measured = runners[case_id](case, path)
        evidence_cases.append({"id": case_id, "domain": case["domain"], "status": "PASS", "source_sha256": case["source_sha256"], "source_size_bytes": case["source_size_bytes"], "expected_digest": _expected_digest(case), "measured": measured})
        print(f"{case_id}: PASS")
    algorithm_files, fingerprint = _algorithm_state(root, list(manifest["algorithm_files"]))
    evidence = {"schema_version": 2, "status": "PASS", "verified_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"), "verified_against_commit": _head(root), "algorithm_fingerprint_scheme": "sha256(sorted(path:git_blob_sha1))", "algorithm_files": algorithm_files, "algorithm_fingerprint": fingerprint, "cases": evidence_cases, "notes": ["Raw bench DAT files were verified from private storage and are intentionally not committed to this public repository.", "BMW response timing uses F-threshold crossing time minus I10% current crossing time."]}
    output = a.output or root / "golden" / "evidence_v09.json"
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    verify(root, manifest_path, output)
    print(f"Evidence refreshed: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
