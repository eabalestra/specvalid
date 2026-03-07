#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# Resolve repository root (parent of this script's directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPECVALID_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
export SPECVALID_DIR

DAIKONDIR="$SPECVALID_DIR/experiments/daikon-5.8.2"
export DAIKONDIR
GASSERT_DIR="$SPECVALID_DIR/experiments/GAssert"
export GASSERT_DIR
SPECS_DIR="$SPECVALID_DIR/experiments/specfuzzer-subject-results"
export SPECS_DIR
MAJOR_HOME="$SPECVALID_DIR/experiments/major"
export MAJOR_HOME

VENV="$SPECVALID_DIR/.venv"
VENV_ACTIVATED=0
SPECVALID_CMD="${SPECVALID_CMD:-specvalid}"

check_dir_exists() {
	local path="$1"
	if [ ! -d "$path" ]; then
		echo "Error: required directory not found: $path"
		echo "Please run setup.sh or ensure the path exists."
		exit 1
	fi
}

activate_venv() {
	if [ -f "$VENV/bin/activate" ]; then
		# shellcheck disable=SC1091
		source "$VENV/bin/activate"
		VENV_ACTIVATED=1
	else
		echo "Virtualenv not found at $VENV; using system Python environment."
	fi
}

deactivate_venv_if_needed() {
	if [ "$VENV_ACTIVATED" -eq 1 ] && type deactivate >/dev/null 2>&1; then
		deactivate
	fi
}

usage() {
	cat <<EOF
Usage: $(basename "$0") -m <model1,model2,...> -p <prompt1,prompt2,...> [-o <output_dir>] [-s <subject>]

Options:
  -m   Comma-separated list of models
  -p   Comma-separated list of prompts
  -o   Output directory (optional, defaults to 'output')
  -s   Run a single subject: "<subject_id> <FullyQualifiedClass> <method>"
  -h   Show this help

Example:
  $(basename "$0") -m "gpt4,gpt4o" -p "promptA,promptB"
  $(basename "$0") -m "gpt4,gpt4o" -p "promptA,promptB" -o "/tmp/experimento1"
  $(basename "$0") -s "QueueAr_getFront DataStructures.QueueAr getFront" -m "GPT51" -p "General_V1"
EOF
	exit 1
}

trap deactivate_venv_if_needed EXIT

MODELS=""
PROMPTS=""
OUTPUT_DIR=""
SINGLE_SUBJECT=""
TEMP_SUBJECTS_FILE=""

cleanup_temp_subjects() {
	if [ -n "${TEMP_SUBJECTS_FILE:-}" ] && [ -f "$TEMP_SUBJECTS_FILE" ]; then
		rm -f "$TEMP_SUBJECTS_FILE"
	fi
	deactivate_venv_if_needed
}

trap cleanup_temp_subjects EXIT

while getopts "m:p:o:s:h" opt; do
	case "$opt" in
	m) MODELS="$OPTARG" ;;
	p) PROMPTS="$OPTARG" ;;
	o) OUTPUT_DIR="$OPTARG" ;;
	s) SINGLE_SUBJECT="$OPTARG" ;;
	h) usage ;;
	*) usage ;;
	esac
done

if [ -z "${MODELS:-}" ] || [ -z "${PROMPTS:-}" ]; then
	echo "Error: both -m and -p are required."
	usage
fi

check_dir_exists "$DAIKONDIR"
check_dir_exists "$GASSERT_DIR"
check_dir_exists "$SPECS_DIR"

if ! command -v python3.12 >/dev/null 2>&1; then
	echo "Error: python3.12 is not installed or not in PATH."
	exit 1
fi

activate_venv

if ! command -v "$SPECVALID_CMD" >/dev/null 2>&1; then
	echo "Error: '$SPECVALID_CMD' is not installed or not in PATH."
	exit 1
fi

# Check API keys for non-local models
check_api_keys() {
	local models="$1"
	local missing_keys=()
	local hf_api_key="${HUGGINGFACE_API_KEY:-${API_KEY_HUGGINGFACE:-}}"

	# Check if models contain non-local providers
	if echo "$models" | grep -qE "(gpt|openai)" && [ -z "${OPENAI_API_KEY:-}" ]; then
		missing_keys+=("OPENAI_API_KEY")
	fi

	if echo "$models" | grep -qE "(claude|anthropic)" && [ -z "${ANTHROPIC_API_KEY:-}" ]; then
		missing_keys+=("ANTHROPIC_API_KEY")
	fi

	if echo "$models" | grep -qE "(gemini|google)" && [ -z "${GOOGLE_API_KEY:-}" ]; then
		missing_keys+=("GOOGLE_API_KEY")
	fi

	if echo "$models" | grep -qE "(huggingface|hf)" && [ -z "$hf_api_key" ]; then
		missing_keys+=("HUGGINGFACE_API_KEY")
	fi

	# Show warnings if keys are missing
	if [ ${#missing_keys[@]} -gt 0 ]; then
		echo "⚠️  WARNING: Missing API keys for non-local models!"
		echo "   The following environment variables are not set:"
		for key in "${missing_keys[@]}"; do
			echo "   - $key"
		done
		echo ""
		echo "   If you're using models that require these keys, the execution will fail."
		echo "   To fix this, export the required API keys:"
		for key in "${missing_keys[@]}"; do
			echo "   export $key=your_api_key_here"
		done
		echo ""
		echo "   Local models (like ollama) don't require API keys."
		echo ""
	fi
}

check_api_keys "$MODELS"

# If -s was given, write a temp subjects file with just that one subject
SUBJECTS_FILE_ARG=""
if [ -n "${SINGLE_SUBJECT:-}" ]; then
	TEMP_SUBJECTS_FILE="$(mktemp /tmp/subjects-to-run.XXXXXX)"
	echo "$SINGLE_SUBJECT" > "$TEMP_SUBJECTS_FILE"
	SUBJECTS_FILE_ARG="--subjects-file \"$TEMP_SUBJECTS_FILE\""
fi

echo "Starting test generation experiments"
echo "  SPECVALID_DIR: $SPECVALID_DIR"
echo "  MODELS: $MODELS"
echo "  PROMPTS: $PROMPTS"
echo "  OUTPUT_DIR: ${OUTPUT_DIR:-default (output)}"
if [ -n "${SINGLE_SUBJECT:-}" ]; then
	echo "  SUBJECT: $SINGLE_SUBJECT"
fi
echo "  Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo ""

# Build arguments for the Python script
PYTHON_ARGS="-m \"$MODELS\" -p \"$PROMPTS\""
if [ -n "${OUTPUT_DIR:-}" ]; then
	PYTHON_ARGS="$PYTHON_ARGS -o \"$OUTPUT_DIR\""
fi
if [ -n "${SUBJECTS_FILE_ARG:-}" ]; then
	PYTHON_ARGS="$PYTHON_ARGS $SUBJECTS_FILE_ARG"
fi

# Run test generation experiments
eval "python3 experiments/run_testgen_experiments_pipeline.py $PYTHON_ARGS"
