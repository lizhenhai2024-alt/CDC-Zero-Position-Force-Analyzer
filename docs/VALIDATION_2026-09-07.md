# Core Validation — 2026-09-07

Validation sample: local MTS `.dat` file supplied during development. Raw customer/test data is **not** committed to the repository.

## Parser

- Parsed rows: 3015
- Repeated `Data Acquisition` blocks: 15
- Required channels recognized:
  - Running Time
  - Axial Displacement
  - Axial Load
  - CDC 1 Current FB_1

## Current / Run recognition

Detected 15 Runs and the expected current sequence:

`0.3, 0.5, 0.7, 0.9, 1.1, 1.3, 1.5, 1.7, 1.5, 1.3, 1.1, 0.9, 0.7, 0.5, 0.3 A`

All display/group labels are rounded to 0.1 A while actual median current is retained.

## Cycle recognition

- 15 complete cycles detected
- 1 complete cycle per Run in this sample
- Block ID and Cycle ID remain separate concepts in the data model

## Audi profile

Rule implemented:

- last complete cycle
- center = `(Xmax + Xmin)/2`
- total evaluation-window width = 10% total stroke
- limits = `center ± 5% total stroke`
- rebound = maximum positive directional force in the window
- compression = minimum negative directional force in the window

Current-level mean results across repeated Runs:

| Current A | Rebound N | Compression N | Runs |
|---:|---:|---:|---:|
| 0.3 | 149.49 | -565.06 | 2 |
| 0.5 | 154.89 | -569.57 | 2 |
| 0.7 | 394.33 | -656.09 | 2 |
| 0.9 | 861.57 | -775.51 | 2 |
| 1.1 | 1159.48 | -842.86 | 2 |
| 1.3 | 1441.20 | -852.39 | 2 |
| 1.5 | 1458.19 | -858.49 | 2 |
| 1.7 | 1469.51 | -859.05 | 1 |

## 2% window-mean check

With a 2% single-sided-amplitude center window, the numerical results closely match zero-crossing interpolation, but this sample's exported time increment is approximately 0.020 s. The narrow window therefore contains fewer than the default 3 points per direction in some/all cycles and is intentionally flagged as `Warning` rather than silently changing the user's window definition.

## Zero crossing check

Linear interpolation at `X=0 mm` produced stable results and serves as an independent diagnostic against the window method.

## Automated tests

`pytest -q`: **5 passed**

Test coverage currently includes:

- repeated MTS block parsing
- multi-cycle detection
- Audi 10%-stroke directional peak rule
- window mean
- zero-crossing interpolation
- constant gas-force correction
- gas-pressure/rod-area force formula

## Known V0.1 limitations / next work

- GUI not yet implemented
- general current-platform segmentation outside MTS block boundaries is intentionally conservative
- incomplete-cycle quality reporting will be expanded
- non-monotonic time / displacement jump checks will be added before V1.0 freeze
- plotting/downsampling and Windows packaging are next-stage work
