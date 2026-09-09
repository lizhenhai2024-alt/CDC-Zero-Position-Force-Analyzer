from __future__ import annotations

import argparse
from pathlib import Path

from .analysis import AnalyzerConfig, CDCAnalyzer, EvaluationProfile
from .export import export_xlsx
from .formatting import dataframe_formatters
from .parser import load_test_data


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="CDC damper center-stroke force analyzer")
    p.add_argument("input", type=Path)
    p.add_argument("--profile", choices=[e.value for e in EvaluationProfile], default=EvaluationProfile.AUDI.value)
    p.add_argument("--gas-force", type=float, default=0.0, help="Constant center gas rebound force [N]")
    p.add_argument(
        "--gas-operation",
        choices=["subtract", "add"],
        default="subtract",
        help="Apply gas force by subtracting it from or adding it to measured load",
    )
    p.add_argument("--corrected", action="store_true", help="Evaluate corrected force instead of measured force")
    p.add_argument("--window-percent", type=float, default=2.0)
    p.add_argument("--window-basis", choices=["amplitude", "total_stroke"], default="amplitude")
    p.add_argument("--zero-target", type=float, default=0.0)
    p.add_argument("--export", type=Path, default=None)
    return p


def main() -> int:
    args = build_parser().parse_args()
    config = AnalyzerConfig(
        profile=EvaluationProfile(args.profile),
        gas_mode="direct" if args.gas_force else "off",
        gas_operation=args.gas_operation,
        gas_force_n=args.gas_force,
        force_channel="corrected" if args.corrected else "raw",
        window_percent=args.window_percent,
        window_basis=args.window_basis,
        zero_target_mm=args.zero_target,
    )
    dataset = load_test_data(args.input)
    result = CDCAnalyzer(config).analyze(dataset)
    print(result.summary.to_string(index=False, formatters=dataframe_formatters(result.summary)))
    if args.export:
        out = export_xlsx(result, args.export)
        print(f"Exported: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
