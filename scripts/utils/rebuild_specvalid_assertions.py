#!/usr/bin/env python3

import argparse
import subprocess
import sys
from pathlib import Path


def read_subjects_file(subjects_file):
    subjects = []
    with open(subjects_file, "r") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 3:
                print(f"Skipping invalid subjects line: {line}")
                continue
            subjects.append((parts[0], parts[1], parts[2]))
    return subjects


def find_model_specs(output_dir, class_name, method_name, model_filter):
    by_model_dir = (
        Path(output_dir) / f"{class_name}_{method_name}" / "test" / "by_model"
    )
    if not by_model_dir.exists():
        print(f"Missing output dir: {by_model_dir}")
        return []

    results = []
    for model_dir in sorted(by_model_dir.iterdir()):
        if not model_dir.is_dir():
            continue
        if model_filter and model_dir.name not in model_filter:
            continue
        specs_dir = model_dir / "specs"
        interest_csv = specs_dir / "interest-specs.csv"
        if not interest_csv.exists():
            print(f"Missing interest-specs.csv: {interest_csv}")
            continue
        results.append((model_dir.name, specs_dir, interest_csv))
    return results


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild specvalid.assertions using existing interest-specs.csv files."
        )
    )
    parser.add_argument(
        "-s",
        "--subjects-file",
        default="experiments/subjects-to-run",
        help="Subjects file with subject, class, and method (default: %(default)s)",
    )
    parser.add_argument(
        "--specs-dir",
        default="experiments/specfuzzer-subject-results",
        help="Base directory for specfuzzer subject results (default: %(default)s)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default="output",
        help="Specvalid output base directory (default: %(default)s)",
    )
    parser.add_argument(
        "-m",
        "--models",
        default="",
        help="Comma-separated model names to include (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without executing them",
    )
    args = parser.parse_args()

    model_filter = {m.strip() for m in args.models.split(",") if m.strip()}

    subjects = read_subjects_file(args.subjects_file)
    if not subjects:
        print(f"No subjects found in {args.subjects_file}")
        return 1

    script_path = Path(__file__).parent / "extract_non_filtered_assertions.py"
    total = 0
    failed = 0
    skipped = 0

    for subject_name, class_fq_name, method_name in subjects:
        class_name = class_fq_name.split(".")[-1]
        specfuzzer_assertions = (
            Path(args.specs_dir)
            / subject_name
            / "output"
            / f"{class_name}-{method_name}-specfuzzer-1.assertions"
        )
        if not specfuzzer_assertions.exists():
            print(f"Skipping (missing specfuzzer assertions): {specfuzzer_assertions}")
            skipped += 1
            continue

        model_specs = find_model_specs(
            args.output_dir, class_name, method_name, model_filter
        )
        if not model_specs:
            print(
                f"No model specs found for {class_name}_{method_name} in {args.output_dir}"
            )
            skipped += 1
            continue

        for model_name, specs_dir, interest_csv in model_specs:
            cmd = [
                sys.executable,
                str(script_path),
                str(specfuzzer_assertions),
                str(interest_csv),
                class_name,
                method_name,
                str(specs_dir),
            ]
            print(f"Rebuilding {class_name}_{method_name} [{model_name}]")
            if args.dry_run:
                print(f"  DRY RUN: {' '.join(cmd)}")
                continue

            result = subprocess.run(cmd, capture_output=True, text=True)
            total += 1
            if result.returncode != 0:
                print(f"  Failed with exit code {result.returncode}")
                if result.stderr:
                    print(result.stderr.strip())
                failed += 1
            elif result.stdout:
                print(result.stdout.strip())

    print(f"Done. Runs: {total}, Skipped: {skipped}, Failed: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
