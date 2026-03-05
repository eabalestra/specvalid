#!/usr/bin/env python3
import argparse
import shutil
from pathlib import Path


def copy_tree(src: Path, dst: Path, dry_run: bool) -> None:
    if dry_run:
        print(f"[DRY RUN] Copy tree {src} -> {dst}")
        return
    shutil.copytree(src, dst, dirs_exist_ok=True)


def copy_logs(src_logs: Path, dst_logs: Path, dry_run: bool) -> None:
    if dry_run:
        print(f"[DRY RUN] Copy logs {src_logs} -> {dst_logs}")
        return
    dst_logs.mkdir(parents=True, exist_ok=True)
    for item in src_logs.iterdir():
        target = dst_logs / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Merge Specvalid outputs by taking assertions/specs from one directory "
            "and logs from another."
        )
    )
    parser.add_argument(
        "--logs-root",
        default="specvalid_outputs_gpt5",
        help="Root directory that contains good logs (default: specvalid_outputs_gpt5)",
    )
    parser.add_argument(
        "--assertions-root",
        default="last_specvalid_outputs_gpt5/output",
        help=(
            "Root directory that contains the desired *.assertions files "
            "(default: last_specvalid_outputs_gpt5/output)"
        ),
    )
    parser.add_argument(
        "--output-root",
        default="merged_specvalid_outputs_gpt5",
        help="Destination directory for merged outputs",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without writing files",
    )
    args = parser.parse_args()

    logs_root = Path(args.logs_root)
    assertions_root = Path(args.assertions_root)
    output_root = Path(args.output_root)

    if not logs_root.exists():
        print(f"Logs root not found: {logs_root}")
        return 1
    if not assertions_root.exists():
        print(f"Assertions root not found: {assertions_root}")
        return 1

    output_root.mkdir(parents=True, exist_ok=True)

    copy_tree(assertions_root, output_root, args.dry_run)

    subjects_in_assertions = {p.name for p in assertions_root.iterdir() if p.is_dir()}
    subjects_in_logs = {p.name for p in logs_root.iterdir() if p.is_dir()}

    copied_logs = 0
    missing_logs = []

    for subject in sorted(subjects_in_assertions):
        src_logs = logs_root / subject / "logs"
        if not src_logs.exists():
            missing_logs.append(subject)
            continue
        dst_logs = output_root / subject / "logs"
        copy_logs(src_logs, dst_logs, args.dry_run)
        copied_logs += 1

    extra_logs = sorted(subjects_in_logs - subjects_in_assertions)

    print(f"Subjects (assertions): {len(subjects_in_assertions)}")
    print(f"Copied logs for: {copied_logs}")
    if missing_logs:
        print("Subjects missing logs:")
        for subject in missing_logs:
            print(f"  {subject}")
    if extra_logs:
        print("Subjects with logs but no assertions:")
        for subject in extra_logs:
            print(f"  {subject}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
