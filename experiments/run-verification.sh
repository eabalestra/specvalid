#!/usr/bin/env bash

set -euo pipefail

usage() {
	cat <<'EOF'
Usage: run-verification.sh -m <models> [options]

Options:
  -m <models>    Comma-separated list of models for specvalid (e.g., "L_Gemma31").
  -o <dir>       Base output directory (passed to --output-dir).
  -s <file>      Subjects file (default: experiments/subjects-to-run).
  -c             Only check required files and exit.
  -h             Show this help message.

Environment: requires GASSERT_DIR, SPECS_DIR (SPECVALID_DIR optional).
EOF
}

# Resolve repository root (parent of this script's directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPECVALID_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
export SPECVALID_DIR

# Tooling and data directories (same layout as run-testgen.sh)
DAIKONDIR="$SPECVALID_DIR/experiments/daikon-5.8.2"
export DAIKONDIR
GASSERT_DIR="$SPECVALID_DIR/experiments/GAssert"
export GASSERT_DIR
SPECS_DIR="$SPECVALID_DIR/experiments/specfuzzer-subject-results"
export SPECS_DIR

VENV="$SPECVALID_DIR/.venv"
VENV_ACTIVATED=0

MODELS=""
PROMPTS="General_V3"
OUTPUT_DIR=""
SUBJECTS_FILE=""
CHECK_ONLY=0

while getopts ":m:o:s:ch" opt; do
	case "$opt" in
	m) MODELS="$OPTARG" ;;
	o) OUTPUT_DIR="$OPTARG" ;;
	s) SUBJECTS_FILE="$OPTARG" ;;
	c) CHECK_ONLY=1 ;;
	h)
		usage
		exit 0
		;;
	:)
		echo "Missing value for -$OPTARG" >&2
		usage
		exit 1
		;;
	\?)
		echo "Invalid option: -$OPTARG" >&2
		usage
		exit 1
		;;
		esac
done

if [[ -z "$MODELS" ]]; then
	echo "Error: -m is required" >&2
	usage
	exit 1
fi

PROJECT_ROOT=${SPECVALID_DIR:-"$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"}
cd "$PROJECT_ROOT"

SUBJECTS_FILE=${SUBJECTS_FILE:-"$PROJECT_ROOT/experiments/subjects-to-run"}

check_dir_exists() {
	local path="$1"
	if [ ! -d "$path" ]; then
		echo "Error: required directory not found: $path" >&2
		echo "Please run setup.sh or ensure the path exists." >&2
		exit 1
	fi
}

activate_venv() {
	if [ -f "$VENV/bin/activate" ]; then
		# shellcheck disable=SC1091
		source "$VENV/bin/activate"
		VENV_ACTIVATED=1
	else
		echo "Error: virtualenv not found at $VENV" >&2
		echo "Create it with: python3 -m venv $VENV and install requirements." >&2
		exit 1
	fi
}

deactivate_venv_if_needed() {
	if [ "$VENV_ACTIVATED" -eq 1 ] && type deactivate >/dev/null 2>&1; then
		deactivate
	fi
}

if [[ ! -f "$SUBJECTS_FILE" ]]; then
	echo "Error: $SUBJECTS_FILE not found" >&2
	exit 1
fi

check_dir_exists "$DAIKONDIR"
check_dir_exists "$GASSERT_DIR"
check_dir_exists "$SPECS_DIR"

activate_venv
trap deactivate_venv_if_needed EXIT

success=0
failed=0

while IFS= read -r line; do
	[[ -z "$line" || "$line" =~ ^# ]] && continue

	# shellcheck disable=SC2086
	set -- $line
	subject="$1"
	class_fq="$2"
	method="$3"

	class_name="${class_fq##*.}"
	package_path="${class_fq//./\/}"

	gassert_base="$GASSERT_DIR/subjects/$subject"
	specs_base="$SPECS_DIR/$subject/output"

	java_class_src="$gassert_base/src/main/java/$package_path.java"
	java_test_suite="$gassert_base/src/test/java/testers/${class_name}Tester0.java"
	java_test_driver="$gassert_base/src/test/java/testers/${class_name}TesterDriver.java"
	bucket_assertions_file="$specs_base/${class_name}-${method}-specfuzzer-1-buckets.assertions"

	missing=()
	for f in \
		"$java_class_src" \
		"$java_test_suite" \
		"$java_test_driver" \
		"$bucket_assertions_file"; do
		[[ -f "$f" ]] || missing+=("$f")
	done

	if ((${#missing[@]} > 0)); then
		echo "✗ Missing files for $subject:" >&2
		printf '  - %s\n' "${missing[@]}" >&2
		((++failed))
		continue
	fi

	if ((CHECK_ONLY)); then
		echo "✓ Files OK for $subject"
		((++success))
		continue
	fi

	cmd=(specvalid verify-only
		"$java_class_src"
		"$java_test_suite"
		"$java_test_driver"
		"$bucket_assertions_file"
		"$method"
		-m "$MODELS"
		-p "$PROMPTS")

	if [[ -n "$OUTPUT_DIR" ]]; then
		cmd=(specvalid --output-dir "$OUTPUT_DIR" "${cmd[@]:1}")
	fi

	echo "> Running $subject ($class_fq.$method)"

	if "${cmd[@]}"; then
		echo "✓ OK $subject"
		((++success))
	else
		echo "✗ Failed $subject"
		((++failed))
	fi

	echo "------------------------------"
done <"$SUBJECTS_FILE"

echo "Done. Success: $success, Failed: $failed"
