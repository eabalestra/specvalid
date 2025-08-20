#!/bin/bash
# SpecValid Setup Script - Sets up the development environment
set -euo pipefail

echo "=== SpecValid Setup Started ==="

# Setup Python virtual environment
setup_venv() {
    if [ -d ".venv" ]; then
        echo "Virtual environment already exists, activating..."
    else
        echo "Creating new virtual environment..."
        python3 -m venv .venv
    fi
    
    # shellcheck disable=SC1091
    source .venv/bin/activate
    
    echo "Updating pip and installing dependencies..."
    pip install --upgrade pip setuptools wheel
    pip install -r requirements.txt
}

setup_venv

# Environment variables
DAIKONDIR="$(pwd)/experiments/daikon-5.8.2"
export DAIKONDIR
GASSERT_DIR="$(pwd)/experiments/GAssert"
export GASSERT_DIR
SPECS_DIR="$(pwd)/experiments/specfuzzer-subject-results"
export SPECS_DIR

echo "Environment variables set:"
echo "  DAIKONDIR=$DAIKONDIR"
echo "  GASSERT_DIR=$GASSERT_DIR"
echo "  SPECS_DIR=$SPECS_DIR"
echo ""

echo "=== Setting up SpecFuzzer's Assertions repository ==="
setup_specfuzzer_repo() {
    if [ -d "$SPECS_DIR/.git" ]; then
        echo "Repository already exists, updating..."
        git -C "$SPECS_DIR" pull
    else
        echo "Cloning SpecFuzzer repository..."
        git clone https://github.com/eabalestra/specfuzzer-subject-results.git "$SPECS_DIR"
    fi
}

setup_specfuzzer_repo

# Common download and extract function
download_and_extract() {
    local name="$1"
    local archive_name="$2"
    local url="$3"
    local download_cmd="$4"
    local extract_cmd="$5"
    local target_dir="${6:-experiments}"
    
    local archive_path="experiments/$archive_name"
    
    # Check if already set up
    if [ -f "$archive_path" ] && [ -d "$target_dir" ]; then
        echo "$name already downloaded and extracted, skipping..."
        return 0
    fi
    
    # Extract if archive exists
    if [ -f "$archive_path" ]; then
        echo "$name archive found, extracting..."
        extract_archive "$archive_path" "$extract_cmd"
        return 0
    fi
    
    # Download to temp directory
    echo "Downloading $name..."
    local temp_dir
    temp_dir=$(mktemp -d)
    local original_dir
    original_dir=$(pwd)
    
    cd "$temp_dir" || { echo "Error: Failed to change to temp directory"; rm -rf "$temp_dir"; return 1; }
    
    if eval "$download_cmd '$url'"; then
        # Find downloaded file
        local downloaded_file
        downloaded_file=$(find . -name "*${archive_name##*.}" -type f | head -n1)
        
        if [ -n "$downloaded_file" ]; then
            echo "Moving file to: $archive_path"
            mv "$downloaded_file" "$original_dir/$archive_path"
            cd "$original_dir" && rm -rf "$temp_dir"
            
            # Extract after successful download
            echo "Extracting $name..."
            extract_archive "$archive_path" "$extract_cmd"
            return 0
        else
            echo "Error: No archive found after download"
            cd "$original_dir" && rm -rf "$temp_dir"
            return 1
        fi
    else
        echo "Error: Failed to download $name"
        echo "Please download manually from: $url"
        cd "$original_dir" && rm -rf "$temp_dir"
        return 1
    fi
}

# Extract archive based on type
extract_archive() {
    local archive_path="$1"
    local extract_cmd="$2"
    local cleanup="${3:-true}"  # Default to true for cleanup
    
    case "$extract_cmd" in
        "tar -xzf")
            if tar -xzf "$archive_path" -C experiments/; then
                if [ "$cleanup" = "true" ]; then
                    echo "Cleaning up archive: $archive_path"
                    rm -f "$archive_path"
                fi
                return 0
            else
                echo "Error: Failed to extract $archive_path"
                return 1
            fi
            ;;
        "unzip -o")
            if unzip -o "$archive_path" -d experiments/; then
                if [ "$cleanup" = "true" ]; then
                    echo "Cleaning up archive: $archive_path"
                    rm -f "$archive_path"
                fi
                return 0
            else
                echo "Error: Failed to extract $archive_path"
                return 1
            fi
            ;;
        *)
            echo "Error: Unknown extraction command: $extract_cmd"
            return 1
            ;;
    esac
}

echo "=== Setting up GAssert ==="
setup_gassert() {
    # Check if gdown is available, install if needed
    if ! command -v gdown >/dev/null 2>&1; then
        echo "Installing gdown for Google Drive downloads..."
        pip install gdown
    fi
    
    download_and_extract "GAssert" "GAssert.tar.gz" \
        'https://drive.google.com/file/d/14QH1LFURZuDvWFJTXS8KYslt9H9S4tt-/view' \
        "gdown --fuzzy" \
        "tar -xzf" \
        "$GASSERT_DIR"
}

setup_gassert

echo "=== Setting up Daikon ==="
setup_daikon() {
    # Check if megadl is available
    if ! command -v megadl >/dev/null 2>&1; then
        echo "Warning: 'megadl' is not installed."
        echo "Please install megatools package:"
        echo "  Ubuntu/Debian: sudo apt-get install megatools"
        echo "  Or download manually from: https://mega.nz/file/pPgmnCST#dObECd8W5VeIDz5xzSgeQnhmH_-BRnOzt1VKaGn7Ihg"
        echo "  Please place the downloaded file (for example 'daikon-5.8.2.zip') into the 'experiments/' directory and re-run this script."
        return 1
    fi
    
    download_and_extract "Daikon" "daikon-5.8.2.zip" \
        'https://mega.nz/file/pPgmnCST#dObECd8W5VeIDz5xzSgeQnhmH_-BRnOzt1VKaGn7Ihg' \
        "megadl" \
        "unzip -o" \
        "$DAIKONDIR"
}

setup_daikon

echo "=== Installing SpecValid package ==="
install_package() {
    if pip install -e .; then
        echo "SpecValid package installed successfully"
    else
        echo "Error: Failed to install SpecValid package"
        return 1
    fi
}

install_package

echo "=== Setup completed successfully! ==="