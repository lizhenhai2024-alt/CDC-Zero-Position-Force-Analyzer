# V0.4 engineering validation — 2026-09-07

## Scope

Validation uses the supplied MTS793/MPT DAT file with 15 `Data Acquisition` blocks and CDC feedback-current sweep from 0.3 A to 1.7 A and back down.

This validation is intended to verify parser/segmentation/evaluation traceability. It does **not** introduce a customer pass/fail limit for sampling rate, sweep hysteresis, or force difference.

## Raw-data preflight

- Acquisition blocks: 15
- Parsed rows: 3015
- Data Quality status: all 15 blocks `OK`
- Calculated sampling frequency: approximately 49.95 Hz
- CDC feedback-current standard deviation per block: approximately 0.0002 A
- Displacement stroke: approximately 100 mm
- Required channels are finite and block timestamps are increasing

The V0.4 GUI therefore allows analysis and shows the diagnostics in the `Data Quality` tab. Structurally invalid input is blocked before engineering evaluation.

## Audi profile — selected last complete cycle

Audi evaluation remains:

- use the last complete cycle in each current run;
- define the evaluation window as the center 10% of total stroke (±5% of total stroke around the cycle center);
- rebound result = maximum load in the rebound branch within the window;
- compression result = minimum load in the compression branch within the window.

### Up / down current sweep comparison

`Delta = Down - Up`.

| Current A | Up Rebound N | Down Rebound N | Delta Rebound N | Up Compression N | Down Compression N | Delta Compression N |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.3 | 150.99 | 147.99 | -3.00 | -561.60 | -568.51 | -6.91 |
| 0.5 | 154.04 | 155.75 | 1.71 | -568.66 | -570.48 | -1.82 |
| 0.7 | 362.85 | 425.81 | 62.97 | -648.33 | -663.84 | -15.51 |
| 0.9 | 839.93 | 883.20 | 43.27 | -770.11 | -780.91 | -10.80 |
| 1.1 | 1145.50 | 1173.46 | 27.97 | -838.76 | -846.96 | -8.20 |
| 1.3 | 1425.34 | 1457.06 | 31.72 | -845.45 | -859.32 | -13.87 |
| 1.5 | 1456.79 | 1459.60 | 2.81 | -858.00 | -858.98 | -0.98 |
| 1.7 | 1469.51 | — | — | -859.05 | — | — |

The 1.7 A point is the sweep turning point and has no separate decreasing-current run in this file, so V0.4 reports `Up only` rather than fabricating a paired result.

The largest rebound up/down differences in this sample occur around 0.7 A and 0.9 A. This is reported descriptively only. A pass/fail judgement requires an explicit engineering or customer tolerance.

## V0.4 traceability changes

- `Data Quality` tab in the desktop GUI;
- structural invalid-data preflight before analysis;
- `Sweep Comparison` tab preserving Up and Down results separately;
- Excel export adds both `Sweep Comparison` and `Data Quality` sheets;
- force/current display precision remains presentation-only and does not round internal calculations;
- no hidden averaging is used for the sweep-comparison table.

## Acceptance intent before V1.0

V0.4 should be manually checked on a Windows workstation for:

1. opening the supplied DAT;
2. correct Data Quality status and block count;
3. Current / Run / Cycle filtering;
4. F-X plot and Audi 10% window overlay;
5. rebound/compression marker positions;
6. Up/Down sweep table values;
7. gas-force correction switch;
8. Excel and PNG export;
9. behavior on at least one deliberately damaged DAT/CSV input.

Any discrepancy found in manual operation should first be converted into a reproducible regression test before the code is changed.
