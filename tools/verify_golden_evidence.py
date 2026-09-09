from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Golden gate: missing {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Golden gate: invalid JSON in {path}: {exc}") from exc


def _git_blob_sha(root: Path, relpath: str) -> str:
    proc = subprocess.run(
        ["git", "ls-tree", "HEAD", "--", relpath],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode == 0 and proc.stdout.strip():
        fields = proc.stdout.strip().split()
        if len(fields) >= 3 and fields[1] == "blob" and HEX40.fullmatch(fields[2]):
            return fields[2]
    path = root / relpath
    if not path.is_file():
        raise SystemExit(f"Golden gate: frozen algorithm file missing: {relpath}")
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def _algorithm_state(root: Path, paths: list[str]) -> tuple[dict[str, str], str]:
    state = {path: _git_blob_sha(root, path) for path in paths}
    payload = "\n".join(f"{path}:{state[path]}" for path in sorted(state))
    return state, hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _expected_digest(case: dict[str, Any]) -> str:
    payload = json.dumps(case["expected"], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _fail(errors: list[str]) -> None:
    if errors:
        print("GOLDEN GATE: FAIL", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        raise SystemExit(1)


def verify(root: Path, manifest_path: Path, evidence_path: Path) -> None:
    manifest = _load_json(manifest_path)
    evidence = _load_json(evidence_path)
    errors: list[str] = []

    if manifest.get("schema_version") != 2:
        errors.append("manifest schema_version must be 2")
    if evidence.get("schema_version") != 2:
        errors.append("evidence schema_version must be 2")
    if manifest.get("status") != "validated_private_source":
        errors.append("manifest status must be validated_private_source")
    if evidence.get("status") != "PASS":
        errors.append("evidence status must be PASS")

    required_domains = set(manifest.get("required_domains") or [])
    manifest_cases = manifest.get("cases") or []
    case_by_id = {str(case.get("id")): case for case in manifest_cases}
    manifest_domains = {str(case.get("domain")) for case in manifest_cases}
    if not required_domains:
        errors.append("manifest required_domains is empty")
    missing_domains = sorted(required_domains - manifest_domains)
    if missing_domains:
        errors.append(f"manifest missing required domain(s): {', '.join(missing_domains)}")
    if len(case_by_id) != len(manifest_cases):
        errors.append("manifest case IDs are missing or duplicated")

    evidence_cases = evidence.get("cases") or []
    evidence_by_id = {str(case.get("id")): case for case in evidence_cases}
    if len(evidence_by_id) != len(evidence_cases):
        errors.append("evidence case IDs are missing or duplicated")
    if set(evidence_by_id) != set(case_by_id):
        errors.append("evidence case IDs do not exactly match manifest case IDs")

    for case_id, case in case_by_id.items():
        source_hash = str(case.get("source_sha256", ""))
        if not HEX64.fullmatch(source_hash):
            errors.append(f"{case_id}: invalid private source SHA-256")
        if case.get("source_visibility") != "private":
            errors.append(f"{case_id}: source_visibility must remain private")
        ev = evidence_by_id.get(case_id, {})
        if ev.get("status") != "PASS":
            errors.append(f"{case_id}: evidence status is not PASS")
        if ev.get("domain") != case.get("domain"):
            errors.append(f"{case_id}: evidence domain differs from manifest")
        if ev.get("source_sha256") != source_hash:
            errors.append(f"{case_id}: evidence source SHA-256 differs from manifest")
        if ev.get("source_size_bytes") != case.get("source_size_bytes"):
            errors.append(f"{case_id}: evidence source size differs from manifest")
        if ev.get("expected_digest") != _expected_digest(case):
            errors.append(f"{case_id}: approved expected outputs changed without a new private Golden run")

    algorithm_files = manifest.get("algorithm_files") or []
    if len(algorithm_files) != len(set(algorithm_files)) or not algorithm_files:
        errors.append("manifest algorithm_files must be a non-empty unique list")
    else:
        current_files, current_fingerprint = _algorithm_state(root, list(algorithm_files))
        evidence_files = evidence.get("algorithm_files") or {}
        if set(evidence_files) != set(algorithm_files):
            errors.append("evidence algorithm file set differs from manifest")
        else:
            for path in algorithm_files:
                expected_blob = str(evidence_files.get(path, ""))
                if not HEX40.fullmatch(expected_blob):
                    errors.append(f"{path}: invalid evidence Git blob SHA")
                elif current_files[path] != expected_blob:
                    errors.append(f"{path}: algorithm changed ({expected_blob[:8]} -> {current_files[path][:8]}); re-run private Golden validation")
        if evidence.get("algorithm_fingerprint") != current_fingerprint:
            errors.append("algorithm fingerprint is stale; re-run private Golden validation")

    _fail(errors)
    print("GOLDEN GATE: PASS | " f"{len(manifest_cases)} private real-bench case(s) | " f"{len(required_domains)}/{len(required_domains)} required domain(s) | " f"algorithm {evidence['algorithm_fingerprint'][:12]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify that committed private-Golden evidence is complete and fresh.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = args.manifest or root / "golden" / "manifest.json"
    evidence = args.evidence or root / "golden" / "evidence_v09.json"
    verify(root, manifest, evidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
