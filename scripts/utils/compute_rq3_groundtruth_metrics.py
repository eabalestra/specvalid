#!/usr/bin/env python3
import argparse
import csv
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
sys.path.append(str(SRC_ROOT))

from specs.specs import Specs  # noqa: E402

VERDICT_TOKEN_MAP = {
    "OK": "OK",
    "FAILED": "FAILED",
    "VALID": "OK",
    "INVALID": "FAILED",
}

VERDICT_PATTERNS = [
    re.compile(
        r"\[\[VERDICT\]\]\s*(OK|FAILED|VALID|INVALID)",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\bVERDICT\b\s*[:=\-]\s*(OK|FAILED|VALID|INVALID)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bverdict\b\s+is\s+\"?(OK|FAILED|VALID|INVALID)\"?",
        re.IGNORECASE,
    ),
]

TEST_NONE_RE = re.compile(r"\[\[TEST\]\]\s*NONE", re.IGNORECASE)
TEST_MARKER_RE = re.compile(r"\[\[TEST\]\]", re.IGNORECASE)
JUNIT_TEST_RE = re.compile(r"^\s*@Test\b", re.MULTILINE)


def normalize_spec(spec: str) -> str:
    return " ".join(spec.strip().split())


def _normalize_verdict(token: str) -> str | None:
    return VERDICT_TOKEN_MAP.get(token.upper())


def parse_verdict(response_text: str) -> str | None:
    for pattern in VERDICT_PATTERNS:
        match = pattern.search(response_text)
        if match:
            return _normalize_verdict(match.group(1))

    if TEST_NONE_RE.search(response_text):
        return "OK"
    if TEST_MARKER_RE.search(response_text):
        return "FAILED"
    if JUNIT_TEST_RE.search(response_text):
        return "FAILED"

    for line in response_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        normalized = _normalize_verdict(stripped)
        if normalized:
            return normalized

    return None


def response_has_test(response_text: str) -> bool:
    if TEST_NONE_RE.search(response_text):
        return False
    if TEST_MARKER_RE.search(response_text):
        return True
    if JUNIT_TEST_RE.search(response_text):
        return True
    return False


def read_subjects(subjects_file: Path) -> list[dict]:
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
            class_name = class_fq.split(".")[-1]
            subjects.append(
                {
                    "subject": subject,
                    "class_fq": class_fq,
                    "class_name": class_name,
                    "method": method,
                    "subject_id": f"{class_name}_{method}",
                }
            )
    return subjects


def normalize_prompt_id(prompt_id: str) -> str:
    cleaned = prompt_id.strip()
    if cleaned.lower() in {"1", "v1", "general_v1"}:
        return "PromptID.General_V1"
    if cleaned.lower() in {"2", "v2", "general_v2"}:
        return "PromptID.General_V2"
    if cleaned.lower() in {"3", "v3", "general_v3"}:
        return "PromptID.General_V3"
    if not cleaned.startswith("PromptID."):
        return f"PromptID.{cleaned}"
    return cleaned


def class_src_path(gassert_dir: Path, subject: str, class_fq: str) -> Path:
    package_path = class_fq.replace(".", "/")
    return (
        gassert_dir
        / "subjects"
        / subject
        / "src"
        / "main"
        / "java"
        / f"{package_path}.java"
    )


def parse_testgen_log(log_path: Path) -> list[dict]:
    rows = []
    lines = log_path.read_text().splitlines()
    i = 0
    current_assertion = None
    assertion_re = re.compile(r"Generating test for assertion:\s*(.*)$")
    response_re = re.compile(
        r"LLM response for prompt ([^ ]+) and model ([^:]+):\s*(.*)$"
    )

    while i < len(lines):
        line = lines[i]
        assertion_match = assertion_re.search(line)
        if assertion_match:
            current_assertion = normalize_spec(assertion_match.group(1))
            i += 1
            continue

        response_match = response_re.search(line)
        if response_match and current_assertion:
            prompt_id = response_match.group(1)
            model_id = response_match.group(2).strip()
            response_lines = [response_match.group(3)]
            i += 1
            while i < len(lines) and not lines[i].startswith("INFO:logger_"):
                response_lines.append(lines[i])
                i += 1
            response_text = "\n".join(response_lines).strip()
            verdict = parse_verdict(response_text)
            rows.append(
                {
                    "assertion": current_assertion,
                    "model_id": model_id,
                    "prompt_id": prompt_id,
                    "verdict": verdict or "UNKNOWN",
                    "has_test": response_has_test(response_text),
                }
            )
            continue

        i += 1

    return rows


def parse_buckets_assertions_path(log_path: Path) -> Path | None:
    patterns = [
        re.compile(r"buckets_assertions_file='([^']+)'"),
        re.compile(r'buckets_assertions_file="([^"]+)"'),
        re.compile(r"buckets_assertions_file=([^,\s)]+)"),
    ]
    for line in log_path.read_text().splitlines():
        for pattern in patterns:
            match = pattern.search(line)
            if match:
                return Path(match.group(1))
    return None


def resolve_buckets_path(
    buckets_path: Path | None,
    subject_name: str,
    class_name: str,
    method: str,
) -> Path | None:
    candidates: list[Path] = []
    if buckets_path:
        if buckets_path.exists():
            return buckets_path
        marker = "experiments/specfuzzer-subject-results"
        buckets_str = str(buckets_path)
        if marker in buckets_str:
            suffix = buckets_str.split(marker, 1)[1].lstrip("/\\")
            candidates.append(REPO_ROOT / marker / suffix)

    candidates.append(
        REPO_ROOT
        / "experiments"
        / "specfuzzer-subject-results"
        / subject_name
        / "output"
        / f"{class_name}-{method}-specfuzzer-1-buckets.assertions"
    )

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def build_raw_spec_map(
    buckets_path: Path, class_path_src: Path, method: str
) -> dict[str, list[str]]:
    spec_transformer = Specs(str(buckets_path), str(class_path_src), method)
    raw_specs = spec_transformer.parse_and_collect_specs()
    mapping: dict[str, list[str]] = defaultdict(list)
    for raw in sorted(raw_specs):
        transformed = normalize_spec(spec_transformer.transform_specification_vars(raw))
        mapping[transformed].append(raw.strip())

    for key, values in mapping.items():
        mapping[key] = sorted(set(values))

    return mapping


def parse_ground_truth_file(
    gt_path: Path, class_path_src: Path, method: str
) -> set[str]:
    spec_transformer = Specs(str(gt_path), str(class_path_src), method)
    result = set()
    for line in gt_path.read_text().splitlines():
        raw = line.strip()
        if not raw:
            continue
        if not spec_transformer._is_inv_line(raw):
            continue
        transformed = normalize_spec(spec_transformer.transform_specification_vars(raw))
        result.add(transformed)
    return result


def load_ground_truth_sets(
    gt_root: Path, subjects_index: dict[tuple[str, str], dict]
) -> dict[str, dict[str, set[str]]]:
    gt_by_subject: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {"valid": set(), "invalid": set()}
    )
    for gt_file in gt_root.glob("**/valid_*.assertions"):
        stem = gt_file.stem[len("valid_") :]
        parts = stem.split("-")
        if len(parts) < 3:
            continue
        class_name, method = parts[0], parts[1]
        subject_entry = subjects_index.get((class_name, method))
        if not subject_entry:
            continue
        class_src = subject_entry["class_src"]
        gt_by_subject[subject_entry["subject_id"]]["valid"].update(
            parse_ground_truth_file(gt_file, class_src, method)
        )

    for gt_file in gt_root.glob("**/invalid_*.assertions"):
        stem = gt_file.stem[len("invalid_") :]
        parts = stem.split("-")
        if len(parts) < 3:
            continue
        class_name, method = parts[0], parts[1]
        subject_entry = subjects_index.get((class_name, method))
        if not subject_entry:
            continue
        class_src = subject_entry["class_src"]
        gt_by_subject[subject_entry["subject_id"]]["invalid"].update(
            parse_ground_truth_file(gt_file, class_src, method)
        )
    return gt_by_subject


def parse_compiled_specs(
    compiled_tests_path: Path, class_path_src: Path, method: str
) -> set[str]:
    if not compiled_tests_path.exists():
        return set()
    spec_transformer = Specs(str(compiled_tests_path), str(class_path_src), method)
    compiled_specs = set()
    for line in compiled_tests_path.read_text().splitlines():
        if "// Spec:" not in line:
            continue
        raw_spec = line.split("// Spec:", 1)[1].strip()
        if not raw_spec:
            continue
        transformed = spec_transformer.transform_specification_vars(raw_spec)
        compiled_specs.add(normalize_spec(transformed))
    return compiled_specs


def main() -> int:
    default_gassert_dir = Path(
        os.environ.get("GASSERT_DIR", REPO_ROOT / "experiments" / "GAssert")
    )

    parser = argparse.ArgumentParser(
        description="Compute RQ3 metrics using ground truth validity from candidate-invariant-checkers."
    )
    parser.add_argument(
        "--subjects-file",
        default=str(REPO_ROOT / "experiments" / "subjects-to-run"),
        help="Subjects file (default: experiments/subjects-to-run)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "output"),
        help="Specvalid output directory (default: output)",
    )
    parser.add_argument(
        "--gassert-dir",
        default=str(default_gassert_dir),
        help="GAssert base directory (default: $GASSERT_DIR or experiments/GAssert)",
    )
    parser.add_argument(
        "--ground-truth-dir",
        default=str(REPO_ROOT / "candidate-invariant-checkers"),
        help="Ground truth directory (default: candidate-invariant-checkers)",
    )
    parser.add_argument(
        "--models",
        default="",
        help="Comma-separated model filter (default: all)",
    )
    parser.add_argument(
        "--prompts",
        default="",
        help="Comma-separated prompt filter (default: all)",
    )
    parser.add_argument(
        "--subject",
        default="",
        help="Single subject id to process (e.g., RingBuffer_remove)",
    )
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "experiments" / "rq3_groundtruth_counterexamples.csv"),
        help="Output CSV for per-assertion rows",
    )
    parser.add_argument(
        "--summary-output",
        default=str(
            REPO_ROOT / "experiments" / "rq3_groundtruth_counterexamples_summary.csv"
        ),
        help="Output CSV for per-model summary",
    )
    args = parser.parse_args()

    subjects = read_subjects(Path(args.subjects_file))
    subjects_index = {}
    for entry in subjects:
        class_src = class_src_path(
            Path(args.gassert_dir), entry["subject"], entry["class_fq"]
        )
        entry["class_src"] = class_src
        subjects_index[(entry["class_name"], entry["method"])] = entry

    if args.subject:
        subjects = [s for s in subjects if s["subject_id"] == args.subject]
        if not subjects:
            print(f"No subject matched: {args.subject}")
            return 1

    ground_truth = load_ground_truth_sets(Path(args.ground_truth_dir), subjects_index)
    model_filter = {m.strip() for m in args.models.split(",") if m.strip()}
    prompt_filter = {
        normalize_prompt_id(p) for p in args.prompts.split(",") if p.strip()
    }

    per_assertion_rows = []
    summary_counts = defaultdict(
        lambda: {
            "failed_total": 0,
            "failed_with_test": 0,
            "failed_compiled": 0,
            "failed_gt_invalid": 0,
            "failed_gt_unknown": 0,
        }
    )

    for entry in subjects:
        subject_id = entry["subject_id"]
        subject_output_dir = Path(args.output_dir) / subject_id
        testgen_log = subject_output_dir / "logs" / "testgen.log"
        if not testgen_log.exists():
            print(f"Missing testgen log: {testgen_log}")
            continue

        log_rows = parse_testgen_log(testgen_log)
        if not log_rows:
            print(f"No verdicts parsed in {testgen_log}")
            continue

        class_src = entry["class_src"]
        if not class_src.exists():
            print(f"Missing class source: {class_src}")
            continue

        models_dir = subject_output_dir / "test" / "by_model"
        if not models_dir.exists():
            print(f"Missing models dir: {models_dir}")
            continue

        filtered_gt = ground_truth.get(subject_id, {"valid": set(), "invalid": set()})
        compiled_specs_by_model = {}
        for model_dir in models_dir.iterdir():
            if not model_dir.is_dir():
                continue
            model_id = model_dir.name
            if model_filter and model_id not in model_filter:
                continue
            compiled_tests_path = model_dir / "compiled_tests.java"
            compiled_specs_by_model[model_id] = parse_compiled_specs(
                compiled_tests_path, class_src, entry["method"]
            )

        raw_spec_map: dict[str, list[str]] = {}
        buckets_path = parse_buckets_assertions_path(testgen_log)
        resolved_buckets_path = resolve_buckets_path(
            buckets_path, entry["subject"], entry["class_name"], entry["method"]
        )
        if resolved_buckets_path and resolved_buckets_path.exists():
            raw_spec_map = build_raw_spec_map(
                resolved_buckets_path, class_src, entry["method"]
            )
        else:
            print(f"Missing buckets assertions for {subject_id} (raw specs not found)")

        for row in log_rows:
            model_id = row["model_id"]
            if model_filter and model_id not in model_filter:
                continue
            prompt_id = row["prompt_id"]
            if prompt_filter and prompt_id not in prompt_filter:
                continue
            if model_id not in compiled_specs_by_model:
                continue

            assertion = row["assertion"]
            verdict = row["verdict"]
            has_test = row["has_test"]
            compiled_set = compiled_specs_by_model[model_id]
            compiled = assertion in compiled_set
            raw_specs = raw_spec_map.get(assertion, [])
            raw_spec_value = " || ".join(raw_specs) if raw_specs else ""

            if assertion in filtered_gt["invalid"]:
                gt_status = "invalid"
            elif assertion in filtered_gt["valid"]:
                gt_status = "valid"
            else:
                gt_status = "unknown"

            per_assertion_rows.append(
                {
                    "subject": subject_id,
                    "model_id": model_id,
                    "prompt_id": prompt_id,
                    "assertion": assertion,
                    "raw_spec": raw_spec_value,
                    "verdict": verdict,
                    "has_test": str(has_test),
                    "compiled": str(compiled),
                    "gt_status": gt_status,
                }
            )

            if verdict != "FAILED":
                continue

            summary_key = (subject_id, model_id, prompt_id)
            summary_counts[summary_key]["failed_total"] += 1
            if gt_status == "unknown":
                summary_counts[summary_key]["failed_gt_unknown"] += 1
            if has_test:
                summary_counts[summary_key]["failed_with_test"] += 1
                if compiled:
                    summary_counts[summary_key]["failed_compiled"] += 1
                    if gt_status == "invalid":
                        summary_counts[summary_key]["failed_gt_invalid"] += 1

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "subject",
                "model_id",
                "prompt_id",
                "assertion",
                "raw_spec",
                "verdict",
                "has_test",
                "compiled",
                "gt_status",
            ],
        )
        writer.writeheader()
        writer.writerows(per_assertion_rows)

    summary_path = Path(args.summary_output)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "subject",
                "model_id",
                "prompt_id",
                "failed_total",
                "failed_with_test",
                "failed_compiled",
                "failed_gt_invalid",
                "failed_gt_unknown",
                "success_rate_failed",
                "success_rate_with_test",
                "compile_rate",
            ],
        )
        writer.writeheader()
        for (subject_id, model_id, prompt_id), counts in sorted(summary_counts.items()):
            failed_total = counts["failed_total"]
            failed_with_test = counts["failed_with_test"]
            failed_compiled = counts["failed_compiled"]
            failed_gt_invalid = counts["failed_gt_invalid"]
            failed_gt_unknown = counts["failed_gt_unknown"]
            success_rate_failed = (
                failed_gt_invalid / failed_total if failed_total else ""
            )
            success_rate_with_test = (
                failed_gt_invalid / failed_with_test if failed_with_test else ""
            )
            compile_rate = (
                failed_compiled / failed_with_test if failed_with_test else ""
            )
            writer.writerow(
                {
                    "subject": subject_id,
                    "model_id": model_id,
                    "prompt_id": prompt_id,
                    "failed_total": failed_total,
                    "failed_with_test": failed_with_test,
                    "failed_compiled": failed_compiled,
                    "failed_gt_invalid": failed_gt_invalid,
                    "failed_gt_unknown": failed_gt_unknown,
                    "success_rate_failed": success_rate_failed,
                    "success_rate_with_test": success_rate_with_test,
                    "compile_rate": compile_rate,
                }
            )

    print(f"Wrote per-assertion rows to {output_path}")
    print(f"Wrote summary rows to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
