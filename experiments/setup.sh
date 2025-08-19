#!/bin/bash
set -euo pipefail

# Create and activate virtualenv
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

# Update pip and install deps
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# Variables (adjust if necessary)
export DAIKONDIR=/workspace/daikon-5.8.2
export GASSERT_DIR=/workspace/GAssert
export SPECS_DIR=/workspace/specfuzzer-subject-results
export SPECVALID_DIR=/workspace/specvalid

# Create parent directories if they don't exist
mkdir -p "$(dirname "$SPECS_DIR")" experiments

# Clone or update repo
if [ -d "$SPECS_DIR/.git" ]; then
    echo "Repo already exists, pulling..."
    git -C "$SPECS_DIR" pull
else
    git clone https://github.com/eabalestra/specfuzzer-subject-results.git "$SPECS_DIR"
fi

# Download GAssert with gdown (force filename)
pip install gdown
gdown --fuzzy 'https://drive.google.com/file/d/14QH1LFURZuDvWFJTXS8KYslt9H9S4tt-/view' -O experiments/GAssert.tar.gz
tar -xzf experiments/GAssert.tar.gz -C experiments/

# Download Daikon (use megatools/megadl if available, otherwise warn)
if command -v megadl >/dev/null 2>&1; then
    megadl 'https://mega.nz/file/pPgmnCST#dObECd8W5VeIDz5xzSgeQnhmH_-BRnOzt1VKaGn7Ihg' -o experiments/daikon-5.8.2.zip
else
    echo "Warning: 'megadl' is not installed. Manual download required: https://mega.nz/file/pPgmnCST"
fi

# Unzip (if zip exists)
if [ -f experiments/daikon-5.8.2.zip ]; then
    unzip -o experiments/daikon-5.8.2.zip -d experiments/
else
    echo "experiments/daikon-5.8.2.zip not found; skipping unzip."
fi