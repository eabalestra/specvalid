import argparse
import csv
import os
import re
from pathlib import Path

TEST_CALL_RE = re.compile(r"\btest\d+\s*\(")


def read_subjects(subjects_file):
    subjects = []
    with subjects_file.open("r") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split()
            if len(parts) < 3:
                print(f"Skipping malformed line in {subjects_file}: {line.rstrip()}")
                continue
            subject, class_fq, method = parts[0], parts[1], parts[2]
            subjects.append((subject, class_fq, method))
    return subjects


def driver_path_for_subject(gassert_dir, subject, class_fq):
    class_name = class_fq.split(".")[-1] if "." in class_fq else class_fq
    return (
        Path(gassert_dir)
        / "subjects"
        / subject
        / "src"
        / "test"
        / "java"
        / "testers"
        / f"{class_name}TesterDriver.java"
    )


def count_tests_in_driver(driver_path):
    content = driver_path.read_text()
    return len(TEST_CALL_RE.findall(content))


def main():
    repo_root = Path(__file__).resolve().parent.parent.parent
    default_gassert_dir = os.environ.get(
        "GASSERT_DIR", str(repo_root / "experiments" / "GAssert")
    )

    parser = argparse.ArgumentParser(
        description="Count Randoop-generated tests per subject using TesterDriver files."
    )
    parser.add_argument(
        "--subjects-file",
        default=str(repo_root / "experiments" / "subjects"),
        help="Path to the subjects file (default: experiments/subjects)",
    )
    parser.add_argument(
        "--gassert-dir",
        default=default_gassert_dir,
        help="Base GAssert directory (default: $GASSERT_DIR or experiments/GAssert)",
    )
    parser.add_argument(
        "--output",
        default=str(repo_root / "experiments" / "randoop_test_counts.csv"),
        help="Output CSV path (default: experiments/randoop_test_counts.csv)",
    )

    args = parser.parse_args()

    subjects_file = Path(args.subjects_file)
    if not subjects_file.exists():
        raise SystemExit(f"Subjects file not found: {subjects_file}")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for subject, class_fq, method in read_subjects(subjects_file):
        driver_path = driver_path_for_subject(args.gassert_dir, subject, class_fq)
        driver_exists = driver_path.exists()
        test_count = 0
        if driver_exists:
            test_count = count_tests_in_driver(driver_path)
        try:
            driver_path_display = str(driver_path.relative_to(repo_root))
        except ValueError:
            driver_path_display = str(driver_path)

        rows.append(
            {
                "subject": subject,
                "class_fq": class_fq,
                "method": method,
                "driver_path": driver_path_display,
                "driver_exists": driver_exists,
                "test_count": test_count,
            }
        )

    fieldnames = [
        "subject",
        "class_fq",
        "method",
        "driver_path",
        "driver_exists",
        "test_count",
    ]
    with output_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {output_path}")


if __name__ == "__main__":
    main()
