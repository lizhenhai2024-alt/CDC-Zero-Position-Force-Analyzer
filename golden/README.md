# Golden regression evidence

V0.9 uses **real bench data as the release oracle without publishing the raw bench files**.

The three required domains are:

1. `audi_center_window` — Audi last complete cycle, center position, total-stroke 10% evaluation window, rebound maximum and compression minimum.
2. `bmw_hysteresis` — BMW zero-position force at paired rising/falling current levels and hysteresis percentage.
3. `bmw_response` — BMW current-step response at the configured target speed, with timing referenced to the I10% current crossing.

## Public repository contents

`manifest.json` contains only:

- a non-identifying Golden case ID,
- SHA-256 and byte size of the private source DAT,
- approved engineering expected outputs,
- numeric comparison tolerances,
- the frozen algorithm file list.

`evidence_v09.json` contains only:

- PASS/FAIL evidence,
- source SHA-256/size confirmation,
- expected-output digests,
- Git blob SHAs of the frozen algorithm files,
- an aggregate algorithm fingerprint,
- compact measured evidence.

**Raw DAT waveforms are intentionally not committed to this public repository.**

## Public CI gate

Run:

```bash
python tools/verify_golden_evidence.py
```

The command fails when any of the following is true:

- one of the three required Golden domains is missing;
- a Golden case is not PASS;
- source hash/size evidence differs from the manifest;
- approved expected outputs were edited without refreshing evidence;
- any frozen algorithm file changed since the private Golden run;
- the aggregate algorithm fingerprint is stale.

The same gate is executed by the normal Windows test workflow, Windows EXE build workflow, and the Windows release workflow.

## Refreshing evidence after an algorithm change

Keep the real DAT files in private/local storage and run from a checked-out repository:

```bash
python tools/run_golden_regression.py ^
  --audi "D:\private\audi_center.dat" ^
  --bmw-hysteresis "D:\private\bmw_hysteresis.dat" ^
  --bmw-response "D:\private\bmw_response_1048.dat"
```

The runner first verifies each private file's SHA-256 and byte size, then executes the current production algorithms and compares the measured results with `manifest.json`. Only a complete 3/3 PASS writes refreshed `evidence_v09.json`.

After review, commit the refreshed evidence together with the intended algorithm change. Do not weaken tolerances merely to make a changed algorithm pass; an expected-output change is an engineering baseline change and must be reviewed as such.

## V1.0 release rule

Do not tag V1.0 unless:

- `python tools/verify_golden_evidence.py` reports PASS,
- the full regression suite passes,
- the Windows executable build succeeds,
- PR/release review confirms that raw bench data remains private.
