#!/usr/bin/env python3
import argparse
import csv
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

# TODO: in my project this script is in scripts/utils/compute_rq2_verdict_metrics.py
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
JSON_KV_VERDICT_RE = re.compile(
    r'"[^"]+"\s*:\s*"?\b(OK|FAILED|VALID|INVALID)\b"?',
    re.IGNORECASE,
)
JSON_VALUE_VERDICT_RE = re.compile(
    r':\s*"?\b(OK|FAILED|VALID|INVALID)\b"?',
    re.IGNORECASE,
)


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

    json_match = JSON_KV_VERDICT_RE.search(response_text)
    if json_match:
        return _normalize_verdict(json_match.group(1))
    if "{" in response_text or "}" in response_text:
        json_match = JSON_VALUE_VERDICT_RE.search(response_text)
        if json_match:
            return _normalize_verdict(json_match.group(1))

    for line in response_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        normalized = _normalize_verdict(stripped)
        if normalized:
            return normalized

    return None


def read_subjects(subjects_file: Path) -> list[tuple[str, str, str]]:
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
            subjects.append((parts[0], parts[1], parts[2]))
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


def load_filtered_specs(specs_dir: Path, class_path_src: Path, method: str) -> set[str]:
    filtered_candidates = list(specs_dir.glob("*-specfuzzer-filtered.assertions"))
    if not filtered_candidates:
        raise FileNotFoundError(f"No filtered assertions file found in {specs_dir}")
    filtered_path = filtered_candidates[0]
    spec_transformer = Specs(str(filtered_path), str(class_path_src), method)
    filtered = set()
    with filtered_path.open("r") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            if not spec_transformer._is_inv_line(raw):
                continue
            transformed = spec_transformer.transform_specification_vars(raw)
            filtered.add(normalize_spec(transformed))
    return filtered


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
                }
            )
            continue

        i += 1

    return rows


def classify(verdict: str, is_filtered: bool) -> str:
    if verdict == "FAILED" and is_filtered:
        return "TP"
    if verdict == "FAILED" and not is_filtered:
        return "FP"
    if verdict == "OK" and not is_filtered:
        return "TN"
    if verdict == "OK" and is_filtered:
        return "FN"
    return "UNKNOWN"


def main() -> int:
    default_gassert_dir = Path(
        os.environ.get("GASSERT_DIR", REPO_ROOT / "experiments" / "GAssert")
    )

    parser = argparse.ArgumentParser(
        description="Compute TP/FP/TN/FN per assertion using testgen logs and filtered specs."
    )
    parser.add_argument(
        "--subjects-file",
        default=str(REPO_ROOT / "experiments" / "subjects-to-run"),
        help="Subjects file (default: experiments/subjects)",
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
        default=str(REPO_ROOT / "experiments" / "rq2_verdicts.csv"),
        help="Output CSV for per-assertion rows",
    )
    parser.add_argument(
        "--summary-output",
        default=str(REPO_ROOT / "experiments" / "rq2_verdicts_summary.csv"),
        help="Output CSV for per-model summary",
    )
    args = parser.parse_args()

    subjects_file = Path(args.subjects_file)
    output_dir = Path(args.output_dir)
    gassert_dir = Path(args.gassert_dir)
    model_filter = {m.strip() for m in args.models.split(",") if m.strip()}
    prompt_filter = {
        normalize_prompt_id(p) for p in args.prompts.split(",") if p.strip()
    }

    subjects = read_subjects(subjects_file)
    if args.subject:
        subjects = [
            s for s in subjects if f"{s[1].split('.')[-1]}_{s[2]}" == args.subject
        ]
        if not subjects:
            print(f"No subject matched: {args.subject}")
            return 1

    per_assertion_rows = []
    summary_counts = defaultdict(
        lambda: {"TP": 0, "FP": 0, "TN": 0, "FN": 0, "UNKNOWN": 0}
    )

    for subject_name, class_fq, method in subjects:
        class_name = class_fq.split(".")[-1]
        subject_id = f"{class_name}_{method}"
        subject_output_dir = output_dir / subject_id
        testgen_log = subject_output_dir / "logs" / "testgen.log"
        if not testgen_log.exists():
            print(f"Missing testgen log: {testgen_log}")
            continue

        log_rows = parse_testgen_log(testgen_log)
        if not log_rows:
            print(f"No verdicts parsed in {testgen_log}")
            continue

        class_src = class_src_path(gassert_dir, subject_name, class_fq)
        if not class_src.exists():
            print(f"Missing class source: {class_src}")
            continue

        models_dir = subject_output_dir / "test" / "by_model"
        if not models_dir.exists():
            print(f"Missing models dir: {models_dir}")
            continue

        filtered_specs_by_model = {}
        for model_dir in models_dir.iterdir():
            if not model_dir.is_dir():
                continue
            model_id = model_dir.name
            if model_filter and model_id not in model_filter:
                continue
            specs_dir = model_dir / "specs"
            if not specs_dir.exists():
                continue
            try:
                filtered_specs_by_model[model_id] = load_filtered_specs(
                    specs_dir, class_src, method
                )
            except FileNotFoundError as exc:
                print(exc)
                continue

        if not filtered_specs_by_model:
            print(f"No filtered specs found for {subject_id}")
            continue

        raw_spec_map: dict[str, list[str]] = {}
        buckets_path = parse_buckets_assertions_path(testgen_log)
        resolved_buckets_path = resolve_buckets_path(
            buckets_path, subject_name, class_name, method
        )
        if resolved_buckets_path and resolved_buckets_path.exists():
            raw_spec_map = build_raw_spec_map(resolved_buckets_path, class_src, method)
        else:
            print(f"Missing buckets assertions for {subject_id} (raw specs not found)")

        for row in log_rows:
            model_id = row["model_id"]
            if model_filter and model_id not in model_filter:
                continue
            prompt_id = row["prompt_id"]
            if prompt_filter and prompt_id not in prompt_filter:
                continue
            if model_id not in filtered_specs_by_model:
                continue
            assertion = row["assertion"]
            verdict = row["verdict"]
            filtered_set = filtered_specs_by_model[model_id]
            is_filtered = assertion in filtered_set
            label = classify(verdict, is_filtered)
            raw_specs = raw_spec_map.get(assertion, [])
            raw_spec_value = " || ".join(raw_specs) if raw_specs else ""

            per_assertion_rows.append(
                {
                    "subject": subject_id,
                    "model_id": model_id,
                    "prompt_id": prompt_id,
                    "assertion": assertion,
                    "raw_spec": raw_spec_value,
                    "verdict": verdict,
                    "filtered": str(is_filtered),
                    "label": label,
                }
            )

            summary_key = (subject_id, model_id, prompt_id)
            summary_counts[summary_key][label] += 1

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
                "filtered",
                "label",
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
                "TP",
                "FP",
                "TN",
                "FN",
                "UNKNOWN",
                "precision",
                "recall",
            ],
        )
        writer.writeheader()
        # print(summary_counts.items())
        for (subject_id, model_id, prompt_id), counts in sorted(summary_counts.items()):
            tp = counts["TP"]
            fp = counts["FP"]
            fn = counts["FN"]
            precision = tp / (tp + fp) if (tp + fp) > 0 else ""
            recall = tp / (tp + fn) if (tp + fn) > 0 else ""
            writer.writerow(
                {
                    "subject": subject_id,
                    "model_id": model_id,
                    "prompt_id": prompt_id,
                    "TP": counts["TP"],
                    "FP": counts["FP"],
                    "TN": counts["TN"],
                    "FN": counts["FN"],
                    "UNKNOWN": counts["UNKNOWN"],
                    "precision": precision,
                    "recall": recall,
                }
            )

    print("=" * 12)
    print(f"Wrote per-assertion rows to {output_path}")
    print(f"Wrote summary rows to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
