#!/bin/bash

# Script to clean output directories for subjects listed in subjects-to-run
# Usage: ./scripts/clean_output_dirs.sh [subjects-file]

# Get project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default subjects file
SUBJECTS_FILE="${1:-$PROJECT_ROOT/experiments/subjects-to-run}"
OUTPUT_DIR="$PROJECT_ROOT/output"

# Check if subjects file exists
if [ ! -f "$SUBJECTS_FILE" ]; then
	echo "Error: Subjects file not found: $SUBJECTS_FILE"
	exit 1
fi

echo "Reading subjects from: $SUBJECTS_FILE"
echo "Output directory: $OUTPUT_DIR"
echo ""

# Counter for deleted directories
deleted=0
skipped=0

# Read subjects file and process each line
while IFS= read -r line || [ -n "$line" ]; do
	# Skip empty lines and comments
	if [[ -z "$line" || "$line" =~ ^# ]]; then
		continue
	fi

	# Parse the line: subject_name class_fq_name method_name
	read -r subject_name class_fq_name method_name <<<"$line"

	# Extract class name from fully qualified name (last part after .)
	if [[ "$class_fq_name" == *"."* ]]; then
		class_name="${class_fq_name##*.}"
	else
		class_name="$class_fq_name"
	fi

	# Build the output directory name: ClassName_methodName
	output_dir_name="${class_name}_${method_name}"
	full_output_path="$OUTPUT_DIR/$output_dir_name"

	# Check if directory exists and remove it
	if [ -d "$full_output_path" ]; then
		echo "Removing: $full_output_path"
		rm -rf "$full_output_path"
		deleted=$((deleted + 1))
	else
		echo "Skipping (not found): $full_output_path"
		skipped=$((skipped + 1))
	fi

done <"$SUBJECTS_FILE"

echo ""
echo "Done! Deleted: $deleted directories, Skipped: $skipped (not found)"
