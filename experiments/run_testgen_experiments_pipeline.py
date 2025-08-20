#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
from pathlib import Path


def setup_environment():
    """Setup the environment by sourcing the config and activating venv."""
    # Get environment variables
    env = os.environ.copy()

    # Get project root from environment variable or use the parent directory as default
    project_root_str = env.get("SPECVALID_DIR", "")
    if project_root_str:
        project_root = Path(project_root_str)
    else:
        project_root = Path(__file__).parent.parent

    os.chdir(project_root)

    return project_root, env


def get_subject_paths(subject_name, class_fq_name, method_name):
    """
    Generate the file paths for a given subject based on the naming convention.

    Args:
        subject_name: The subject identifier (e.g., 'QueueAr_makeEmpty')
        class_fq_name: Fully qualified class name (e.g., 'DataStructures.QueueAr')
        method_name: Method name (e.g., 'makeEmpty')

    Returns:
        dict: Dictionary containing all required file paths
    """

    # Extract simple class name from fully qualified name
    class_name = class_fq_name.split(".")[-1] if "." in class_fq_name else class_fq_name
    package_path = (
        class_fq_name.replace(".", "/") if "." in class_fq_name else class_fq_name
    )

    gassert_dir = os.environ.get("GASSERT_DIR")
    gassert_base = f"{gassert_dir}/subjects/{subject_name}"

    specs_dir = os.environ.get("SPECS_DIR")
    specfuzzer_output_base = f"{specs_dir}/{subject_name}/output"

    paths = {
        "java_class_src": (f"{gassert_base}/src/main/java/{package_path}.java"),
        "java_test_suite": (
            f"{gassert_base}/src/test/java/testers/" f"{class_name}Tester0.java"
        ),
        "java_test_driver": (
            f"{gassert_base}/src/test/java/testers/" f"{class_name}TesterDriver.java"
        ),
        "bucket_assertions_file": (
            f"{specfuzzer_output_base}/{class_name}-{method_name}-"
            f"specfuzzer-1-buckets.assertions"
        ),
        "specfuzzer_invs_file": (
            f"{specfuzzer_output_base}/{class_name}-{method_name}-"
            f"specfuzzer-1.inv.gz"
        ),
        "specfuzzer_assertions_file": (
            f"{specfuzzer_output_base}/{class_name}-{method_name}-"
            f"specfuzzer-1.assertions"
        ),
        "method": method_name,
    }

    return paths


def check_subject_files(subject_name, paths):
    """
    Check if all required files exist for a subject.

    Args:
        subject_name: The subject identifier
        paths: Dictionary of file paths

    Returns:
        bool: True if all files exist, False otherwise
    """
    missing_files = []

    for key, path in paths.items():
        if key != "method" and not Path(path).exists():
            missing_files.append(f"{key}: {path}")

    if missing_files:
        print(f"✗ Missing files for {subject_name}:")
        for missing in missing_files:
            print(f"  - {missing}")
        return False

    return True


def run_command(command, description, continue_on_error=True, dry_run=False, env=None):
    """
    Run a shell command and return success status.

    Args:
        command: List of command arguments or string command
        description: Description of what the command does
        continue_on_error: Whether to continue if the command fails
        dry_run: If True, just print what would be executed
        env: Environment variables to use for the command

    Returns:
        bool: True if command succeeded, False otherwise
    """
    try:
        print(f"> {description}")

        if dry_run:
            if isinstance(command, str):
                print(f"[DRY RUN] Would execute: {command}")
            else:
                print(f"[DRY RUN] Would execute: {' '.join(command)}")
            return True

        if isinstance(command, str):
            result = subprocess.run(
                command,
                shell=True,
                check=False,
                capture_output=False,
                text=True,
                env=env,
            )
        else:
            result = subprocess.run(
                command, check=False, capture_output=False, text=True, env=env
            )

        if result.returncode == 0:
            print(f"✓ {description} completed successfully")
            return True
        else:
            print(f"✗ {description} failed with exit code {result.returncode}")
            if not continue_on_error:
                sys.exit(result.returncode)
            return False

    except Exception as e:
        print(f"✗ {description} failed with exception: {e}")
        if not continue_on_error:
            sys.exit(1)
        return False


def read_subjects_file(subjects_file):
    """Read and parse the subjects file, filtering out comments."""
    subjects = []

    if not subjects_file.exists():
        print(f"Error: {subjects_file} not found!")
        sys.exit(1)

    with open(subjects_file, "r") as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith("#"):
                subjects.append(line.split())

    return subjects


def build_specvalid_command(paths, models, prompts):
    """
    Build the specvalid command with all required arguments.

    Args:
        paths: Dictionary containing all file paths
        models: Models string
        prompts: Prompts string

    Returns:
        list: Command as list of arguments
    """
    return [
        "specvalid",
        "testgen",
        paths["java_class_src"],
        paths["java_test_suite"],
        paths["java_test_driver"],
        paths["bucket_assertions_file"],
        paths["method"],
        "-m",
        models,
        "-p",
        prompts,
        "-sf",
        paths["specfuzzer_invs_file"],
        "-sa",
        paths["specfuzzer_assertions_file"],
    ]


def main():
    """Main pipeline execution."""
    # Default values
    DEFAULT_MODELS = None
    DEFAULT_PROMPTS = None

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run experiment pipeline")
    parser.add_argument(
        "-m",
        "--models",
        default=DEFAULT_MODELS,
        help=f"Models to use (default: {DEFAULT_MODELS})",
    )
    parser.add_argument(
        "-p",
        "--prompts",
        default=DEFAULT_PROMPTS,
        help=f"Prompts to use (default: {DEFAULT_PROMPTS})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be executed without running it",
    )
    parser.add_argument(
        "--check-files",
        action="store_true",
        help="Check if all required files exist for each subject",
    )

    args = parser.parse_args()

    if args.models is None:
        raise ValueError("Models must be specified")
    if args.prompts is None:
        raise ValueError("Prompts must be specified")

    # Setup environment
    project_root, env = setup_environment()

    # Path to the file containing the list of subjects
    subjects_file = project_root / "experiments" / "subjects-to-run"

    # Read subjects
    subjects = read_subjects_file(subjects_file)
    total_subjects = len(subjects)

    # print("> Running experiment pipeline with the following configuration:")
    # print(f"Models: {args.models}")
    # print(f"Prompts: {args.prompts}")
    # print(f"Subjects file: {subjects_file}")
    # print(f"Total subjects to process: {total_subjects}")
    # print("")

    successful_runs = 0
    failed_runs = 0

    # Process each subject
    for i, subject_args in enumerate(subjects, 1):
        if len(subject_args) < 3:
            print(f"✗ Skipping invalid subject line: {' '.join(subject_args)}")
            failed_runs += 1
            continue

        subject_name = subject_args[0]
        class_name = subject_args[1]
        method_name = subject_args[2]

        # Calculate progress
        percentage = (i * 100) // total_subjects

        print(f"Processing subject: {subject_name}")
        print(f"Class: {class_name}, Method: {method_name}")
        print(f"Progress: {percentage}% ({i}/{total_subjects})")
        print("")

        # Get file paths for this subject
        paths = get_subject_paths(subject_name, class_name, method_name)

        # Override method name from subjects file if different
        paths["method"] = method_name

        # Check if files exist
        if args.check_files or not check_subject_files(subject_name, paths):
            if args.check_files:
                print(f"File check for {subject_name}:")
                check_subject_files(subject_name, paths)
                print("")
                continue
            else:
                print(f"✗ Skipping {subject_name} due to missing files")
                failed_runs += 1
                print("")
                print("-" * 80)
                print("")
                continue

        # Build and run the specvalid command
        cmd = build_specvalid_command(paths, args.models, args.prompts)

        success = run_command(
            cmd,
            f"Running specvalid for {subject_name} ({class_name}.{method_name})",
            continue_on_error=True,
            dry_run=args.dry_run,
            env=env,
        )

        if success:
            print(f"✓ Specvalid completed successfully for {subject_name}")
            successful_runs += 1
        else:
            print(
                f"✗ Specvalid failed for {subject_name} - "
                f"continuing with next subject"
            )
            failed_runs += 1

        print("")
        print("-" * 80)
        print("")

    # Summary
    print("Pipeline completed!")
    print(f"Successful runs: {successful_runs}")
    print(f"Failed runs: {failed_runs}")
    print(f"Total subjects: {total_subjects}")

    # Collect results after processing all subjects (if not in dry run mode)
    if not args.dry_run and successful_runs > 0:
        print("Collecting results...")
        success_collect = run_command(
            ["python3", "experiments/collect_results.py"],
            "Collecting results",
            continue_on_error=False,
            dry_run=args.dry_run,
            env=env,
        )

        if success_collect:
            print("")
            print("Done! All subjects processed.")
            print("Results saved to experiments/results/test_generation_stats.csv")
        else:
            print("Failed to collect results.")
            sys.exit(1)


if __name__ == "__main__":
    main()
