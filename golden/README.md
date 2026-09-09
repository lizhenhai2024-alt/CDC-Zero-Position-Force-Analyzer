# Golden DAT Regression

This directory defines the contract for real-data regression used by V0.9 and V1.0.

## Required case metadata

Each Golden case must define:

- stable case ID;
- original DAT filename;
- SHA-256 of the exact input bytes;
- customer/profile (for example BMW or Audi) when applicable;
- data-column mapping and units;
- evaluation method and window;
- gas-force correction mode and value if used;
- expected rebound/compression outputs;
- expected response metrics when applicable;
- numeric tolerance for each frozen output;
- provenance note explaining where the file came from and why it is representative.

## Rules

1. Real DAT files are the authority for Golden regression.
2. Synthetic test fixtures remain useful for edge cases but are not Golden evidence.
3. Expected results are never updated automatically when code changes.
4. A Golden result change requires an engineering review note explaining the physical or algorithmic reason.
5. Confidential input files may be stored in a private artifact store instead of the public repository. In that case the manifest still records SHA-256 and expected outputs so the exact source can be verified locally/CI.
6. Rebound force > 0 and compression force < 0 are frozen sign conventions.

## Status

The V0.9 framework is active, but no raw real DAT file has yet been admitted into the public Golden set. Do not mark the Golden gate PASS until at least one representative real DAT case is registered and executed in CI or in the approved private regression job.
