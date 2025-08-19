#!/bin/bash


SPECVALID_DIR="$(pwd)"
export SPECVALID_DIR
DAIKONDIR="$SPECVALID_DIR/experiments/daikon-5.8.2"
export DAIKONDIR
GASSERT_DIR="$SPECVALID_DIR/experiments/GAssert"
export GASSERT_DIR
SPECS_DIR="$SPECVALID_DIR/experiments/specfuzzer-subject-results"
export SPECS_DIR

# shellcheck disable=SC1091
source .venv/bin/activate

usage() {
    echo "Usage: $0 -m <model1,model2,...> -p <prompt1,prompt2,...>"
    exit 1
}

MODELS=""
PROMPTS=""

while getopts "m:p:" opt; do
    case "$opt" in
        m) MODELS="$OPTARG" ;;
        p) PROMPTS="$OPTARG" ;;
        *) usage ;;
    esac
done

if [ -z "$MODELS" ] || [ -z "$PROMPTS" ]; then
    usage
fi

# Run test generation experiments
python3 experiments/run_testgen_experiments_pipeline.py -m "$MODELS" -p "$PROMPTS"
