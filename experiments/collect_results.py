import csv
import os
import re


def load_subject_mapping(subjects_file):
    """
    Load the subject mapping from the subjects file.
    Returns a dictionary with subject_name -> (class_name, method_name)
    and a list to maintain order.
    """
    subjects_map = {}
    subjects_order = []

    try:
        with open(subjects_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split()
                    if len(parts) >= 3:
                        subject_name = parts[0]
                        class_name = parts[1]
                        method_name = parts[2]
                        subjects_map[subject_name] = (class_name, method_name)
                        subjects_order.append(subject_name)

    except Exception as e:
        print(f"Error reading subjects file {subjects_file}: {str(e)}")

    return subjects_map, subjects_order


def create_name_mapping(subjects_map, existing_subjects):
    """
    Create a mapping between different naming conventions.
    Maps actual directory names to subject info.
    """
    name_mapping = {}

    # Direct mapping for exact matches
    for subject in existing_subjects:
        if subject in subjects_map:
            name_mapping[subject] = (subject, subjects_map[subject])

    # Handle naming variations - try exact class_method match first
    for existing_subject in existing_subjects:
        if existing_subject not in name_mapping:
            # Convert existing subject to lowercase for comparison
            existing_lower = existing_subject.lower()

            # Try to find exact match by converting subject names to expected format
            for mapped_subject, (class_name, method_name) in subjects_map.items():
                # Create expected directory name from class and method
                class_simple = class_name.split(".")[-1]  # Get last part of class name
                expected_dir = f"{class_simple}_{method_name}"

                # Try multiple variations of expected directory name
                variations = [
                    expected_dir,
                    expected_dir.lower(),
                    f"{class_simple.lower()}_{method_name}",
                    mapped_subject,
                    mapped_subject.lower(),
                ]

                if (
                    existing_subject in variations
                    or existing_lower in [v.lower() for v in variations]
                    or existing_subject.lower() == expected_dir.lower()
                ):
                    mapping_info = (mapped_subject, (class_name, method_name))
                    name_mapping[existing_subject] = mapping_info
                    break

    # Fallback: if still no mapping, use the directory name as-is
    for existing_subject in existing_subjects:
        if existing_subject not in name_mapping:
            # Create a fallback mapping using the directory name
            name_mapping[existing_subject] = (existing_subject, ("", ""))

    return name_mapping


def extract_test_counts(log_file):
    """
    Extract the number of generated and compiled tests from testgen.log.
    Returns: dict with model_id -> {raw_tests, compiled_tests}
    """
    model_test_counts = {}

    try:
        with open(log_file, "r") as f:
            content = f.read()

            # Find all model statistics: "Model {model}: {raw} raw -> {compiled} compiled"
            pattern = r"Model ([^:]+): (\d+) raw -> (\d+) compiled"
            matches = re.findall(pattern, content)

            for model_name, raw_tests, compiled_tests in matches:
                model_test_counts[model_name] = {
                    "raw_tests": int(raw_tests),
                    "compiled_tests": int(compiled_tests),
                }

        return model_test_counts

    except Exception as e:
        print(f"Error processing {log_file}: {str(e)}")
        return {}


def extract_spec_counts(invfilter_log_file):
    """
    Extract the number of filtered specifications from invfilter.log per model.
    Returns: dict with model_id -> filtered_specs_count
    """
    specs_counts_by_model = {}

    try:
        with open(invfilter_log_file, "r") as f:
            content = f.read()

            # Look for model-specific filtering sections
            lines = content.split("\n")
            current_model = None

            for line in lines:
                # Look for "Running invariant filtering for tests from model: {model}"
                model_match = re.search(
                    r"Running invariant filtering for tests from model: (.+)", line
                )
                if model_match:
                    current_model = model_match.group(1).strip()

                # Look for filtered specs count
                if current_model and "Filtered specs:" in line:
                    specs_match = re.search(r"Filtered specs: (\d+)", line)
                    if specs_match:
                        filtered_count = int(specs_match.group(1))
                        specs_counts_by_model[current_model] = filtered_count
                        current_model = None  # Reset after finding the count

        return specs_counts_by_model

    except Exception as e:
        print(f"Error processing {invfilter_log_file}: {str(e)}")
        return {}


def normalize_model_name(model_name):
    """
    Normalize model names to handle inconsistencies like:
    N_DeepSeekR1 vs NDeepSeekR1, N_Llama3370Instruct vs NLlama3370Instruct
    Returns the normalized name (without underscores after N)
    """
    # Remove underscores that appear after N prefix
    if model_name.startswith("N_"):
        return "N" + model_name[2:]
    return model_name


def extract_bucket_specs_counts(bucketing_dir, class_name, method_name):
    """
    Extract the number of specs post-bucket from bucketing directory per model.
    Reads from bucketing/model_{model}/*-specvalid-buckets.assertions
    Returns: dict with model_id -> specs_count (using normalized names)
    """
    bucket_specs_by_model = {}

    if not os.path.exists(bucketing_dir):
        return bucket_specs_by_model

    try:
        for model_dir_name in os.listdir(bucketing_dir):
            model_dir = os.path.join(bucketing_dir, model_dir_name)
            if not os.path.isdir(model_dir) or not model_dir_name.startswith("model_"):
                continue

            # Extract model name from directory name (model_GPT51 -> GPT51)
            model_name = model_dir_name.replace("model_", "")

            # Find the buckets assertions file
            for filename in os.listdir(model_dir):
                if filename.endswith("-specvalid-buckets.assertions"):
                    filepath = os.path.join(model_dir, filename)
                    try:
                        with open(filepath, "r") as f:
                            for line in f:
                                # Look for "specs={count}" line
                                if line.startswith("specs="):
                                    specs_count = int(line.strip().split("=")[1])
                                    bucket_specs_by_model[model_name] = specs_count
                                    break
                    except Exception as e:
                        print(f"Error reading {filepath}: {e}")
                    break

    except Exception as e:
        print(f"Error reading bucketing directory {bucketing_dir}: {e}")

    return bucket_specs_by_model


def count_specs_in_file(filepath):
    """
    Count the number of valid specs in an assertions file.
    """
    if not os.path.exists(filepath):
        return 0

    try:
        with open(filepath, "r") as f:
            specs = {line.strip() for line in f}

        # Filter out separators and special entries
        specs = {
            item
            for item in specs
            if item
            and not item.startswith(
                "==========================================================================="
            )
            and ":::OBJECT" not in item
            and ":::ENTER" not in item
            and ":::EXIT" not in item
        }
        return len(specs)
    except Exception as e:
        print(f"Error reading {filepath}: {str(e)}")
        return 0


def extract_model_stats(model_output_dir):
    """
    Extract statistics for individual models from their directories.
    Returns dict with model stats: {model_id: stats}
    Note: This function is kept for compatibility but most data now comes from logs.
    """
    model_stats = {}
    by_model_dir = os.path.join(model_output_dir, "by_model")

    if not os.path.exists(by_model_dir):
        return model_stats

    for model_name in os.listdir(by_model_dir):
        model_dir = os.path.join(by_model_dir, model_name)
        if not os.path.isdir(model_dir):
            continue

        stats = {
            "raw_tests": 0,
            "compiled_tests": 0,
            "new_specs_filtered": 0,
        }

        # Read metadata files for test counts (if they exist)
        for phase in ["raw", "compiled"]:
            metadata_file = os.path.join(model_dir, f"{phase}_metadata.json")
            if os.path.exists(metadata_file):
                try:
                    import json

                    with open(metadata_file, "r") as f:
                        metadata = json.load(f)
                        test_count = metadata.get("test_count", 0)
                        if phase == "raw":
                            stats["raw_tests"] = test_count
                        elif phase == "compiled":
                            stats["compiled_tests"] = test_count
                except Exception as e:
                    print(f"Error reading {metadata_file}: {e}")

        model_stats[model_name] = stats

    return model_stats


def calculate_success_rates(stats):
    """Calculate success rates: generated -> compiled"""
    generated = stats.get("raw_tests", 0)
    compiled = stats.get("compiled_tests", 0)

    # Overall success rate
    overall_rate = (compiled / generated * 100) if generated > 0 else 0.0

    return overall_rate


def get_best_performing_models(model_results):
    """Identify best performing models by specs filtered, then test success rates"""
    model_performance = {}

    for result in model_results:
        model = result["MODEL"]
        if model not in model_performance:
            model_performance[model] = {
                "subjects": [],
                "total_generated": 0,
                "total_compiled": 0,
                "total_specs_filtered": 0,
            }

        perf = model_performance[model]
        perf["subjects"].append(result["SUBJECT"])
        perf["total_generated"] += result["TESTS_GENERATED_BY_LLM"]
        perf["total_compiled"] += result["TESTS_COMPILED"]
        perf["total_specs_filtered"] += result["NEW_SPECS_FILTERED_PRE-BUCKET"]

    # Calculate aggregate rates for each model
    best_models = []
    for model, perf in model_performance.items():
        best_models.append(
            {
                "MODEL": model,
                "SUBJECTS": len(perf["subjects"]),
                "GENERATED": perf["total_generated"],
                "COMPILED": perf["total_compiled"],
                "NEW_SPECS_FILTERED": perf["total_specs_filtered"],
            }
        )

    # Sort by specifications filtered first, then by tests compiled
    best_models.sort(
        key=lambda x: (x["NEW_SPECS_FILTERED"], x["COMPILED"]), reverse=True
    )

    return best_models


def get_best_model_per_subject(unified_results, subjects_order):
    """Get best model per subject by specs filtered and test success"""
    subjects_summary = {}

    for result in unified_results:
        subject = result["SUBJECT"]
        if subject not in subjects_summary:
            subjects_summary[subject] = []
        subjects_summary[subject].append(result)

    subject_best_models = []

    # Process subjects in the order they appear in the subjects file
    for subject in subjects_order:
        if subject in subjects_summary:
            results = subjects_summary[subject]
            # Sort by specs filtered first, then by tests compiled
            best_result = max(
                results,
                key=lambda x: (
                    x["NEW_SPECS_FILTERED_PRE-BUCKET"],
                    x["TESTS_COMPILED"],
                ),
            )

            subject_best_models.append(
                {
                    "SUBJECT": subject,
                    "CLASS": best_result["CLASS"],
                    "METHOD": best_result["METHOD"],
                    "BEST_MODEL": best_result["MODEL"],
                    "SPECFUZZER_SPECS_PRE-BUCKET": best_result[
                        "SPECFUZZER_SPECS_PRE-BUCKET"
                    ],
                    "SPECFUZZER_SPECS_POST-BUCKET": best_result[
                        "SPECFUZZER_SPECS_POST-BUCKET"
                    ],
                    "TESTS_GENERATED_BY_LLM": best_result["TESTS_GENERATED_BY_LLM"],
                    "TESTS_COMPILED": best_result["TESTS_COMPILED"],
                    "NEW_SPECS_FILTERED_PRE-BUCKET": best_result[
                        "NEW_SPECS_FILTERED_PRE-BUCKET"
                    ],
                    "NEW_SPECS_POST-BUCKET": best_result["NEW_SPECS_POST-BUCKET"],
                }
            )

    # Add any remaining subjects that weren't in the subjects file
    for subject, results in subjects_summary.items():
        if subject not in subjects_order:
            best_result = max(
                results,
                key=lambda x: (
                    x["NEW_SPECS_FILTERED_PRE-BUCKET"],
                    x["TESTS_COMPILED"],
                ),
            )

            subject_best_models.append(
                {
                    "SUBJECT": subject,
                    "CLASS": best_result["CLASS"],
                    "METHOD": best_result["METHOD"],
                    "BEST_MODEL": best_result["MODEL"],
                    "SPECFUZZER_SPECS_PRE-BUCKET": best_result[
                        "SPECFUZZER_SPECS_PRE-BUCKET"
                    ],
                    "SPECFUZZER_SPECS_POST-BUCKET": best_result[
                        "SPECFUZZER_SPECS_POST-BUCKET"
                    ],
                    "TESTS_GENERATED_BY_LLM": best_result["TESTS_GENERATED_BY_LLM"],
                    "TESTS_COMPILED": best_result["TESTS_COMPILED"],
                    "NEW_SPECS_FILTERED_PRE-BUCKET": best_result[
                        "NEW_SPECS_FILTERED_PRE-BUCKET"
                    ],
                    "NEW_SPECS_POST-BUCKET": best_result["NEW_SPECS_POST-BUCKET"],
                }
            )

    return subject_best_models


def main():
    # Base output directory
    base_dir = "output"
    subjects_file = "experiments/subjects"

    # Load subject mapping and order
    subjects_map, subjects_order = load_subject_mapping(subjects_file)

    # List to store results - unified approach
    unified_results = []

    # Find all subject directories that actually exist in output
    existing_subjects = [
        d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))
    ]

    # Create mapping between actual directory names and subject info
    name_mapping = create_name_mapping(subjects_map, existing_subjects)

    # Create ordered list based on subjects file, but using actual directory names
    ordered_existing_subjects = []

    # First, add subjects in the order from subjects file
    for subject in subjects_order:
        # Find the actual directory name that corresponds to this subject
        for existing_subject, (mapped_subject, _) in name_mapping.items():
            if mapped_subject == subject:
                ordered_existing_subjects.append(existing_subject)
                break

    # Add any remaining subjects that weren't in the subjects file
    for existing_subject in existing_subjects:
        if existing_subject not in ordered_existing_subjects:
            ordered_existing_subjects.append(existing_subject)

    # Process subjects in order - collect all data in one pass
    for subject in ordered_existing_subjects:
        # Get class and method names from mapping
        if subject in name_mapping:
            mapped_subject, (class_name, method_name) = name_mapping[subject]
        else:
            mapped_subject, class_name, method_name = subject, "", ""

        # Extract simple class name for file paths
        simple_class_name = (
            class_name.split(".")[-1] if "." in class_name else class_name
        )

        # Paths to the log files and directories
        testgen_log_file = os.path.join(base_dir, subject, "logs", "testgen.log")
        invfilter_log_file = os.path.join(base_dir, subject, "logs", "invfilter.log")
        bucketing_dir = os.path.join(base_dir, subject, "bucketing")
        test_output_dir = os.path.join(base_dir, subject, "test")

        # Try to get specs from specfuzzer-subject-results
        specs_dir = os.environ.get(
            "SPECS_DIR", "experiments/specfuzzer-subject-results"
        )

        # PRE-BUCKET: Read from .assertions file (before bucketing)
        pre_bucket_file = os.path.join(
            specs_dir,
            mapped_subject,
            "output",
            f"{simple_class_name}-{method_name}-specfuzzer-1.assertions",
        )
        specs_pre_bucket = count_specs_in_file(pre_bucket_file)

        # POST-BUCKET: Read from -buckets.assertions file (after bucketing)
        post_bucket_file = os.path.join(
            specs_dir,
            mapped_subject,
            "output",
            f"{simple_class_name}-{method_name}-specfuzzer-1-buckets.assertions",
        )
        specs_post_bucket = count_specs_in_file(post_bucket_file)

        # Extract test counts per model from testgen.log
        model_test_counts = {}
        if os.path.exists(testgen_log_file):
            model_test_counts = extract_test_counts(testgen_log_file)

        # Extract NEW_SPECS_FILTERED_PRE-BUCKET per model from invfilter.log
        specs_filtered_by_model = {}
        if os.path.exists(invfilter_log_file):
            specs_filtered_by_model = extract_spec_counts(invfilter_log_file)

        # Extract NEW_SPECS_POST-BUCKET per model from bucketing directory
        bucket_specs_by_model = {}
        if os.path.exists(bucketing_dir):
            bucket_specs_by_model = extract_bucket_specs_counts(
                bucketing_dir, simple_class_name, method_name
            )

        # Get list of all models from test output dir
        model_stats = extract_model_stats(test_output_dir)

        # Collect all model names and normalize them
        # Use model names from testgen.log as the canonical source
        all_models = set()
        for m in model_test_counts.keys():
            all_models.add(m)

        # If no models from testgen, use other sources
        if not all_models:
            all_models.update(model_stats.keys())
            all_models.update(specs_filtered_by_model.keys())

        # Create unified results with proper priority ordering
        for model_id in all_models:
            # Get test counts from testgen.log (primary source)
            test_data = model_test_counts.get(model_id, {})
            raw_tests = test_data.get("raw_tests", 0)
            compiled_tests = test_data.get("compiled_tests", 0)

            # Fall back to metadata if testgen.log doesn't have data
            if raw_tests == 0 and model_id in model_stats:
                raw_tests = model_stats[model_id].get("raw_tests", 0)
                compiled_tests = model_stats[model_id].get("compiled_tests", 0)

            # NEW_SPECS_FILTERED_PRE-BUCKET from invfilter.log
            new_specs_filtered = specs_filtered_by_model.get(model_id, 0)

            # NEW_SPECS_POST-BUCKET from bucketing directory
            # Need to normalize model name (N_Llama3370Instruct -> NLlama3370Instruct)
            normalized_model = normalize_model_name(model_id)
            new_specs_post_bucket = bucket_specs_by_model.get(normalized_model, 0)

            # Also try with the original name
            if new_specs_post_bucket == 0:
                new_specs_post_bucket = bucket_specs_by_model.get(model_id, 0)

            unified_result = {
                "SUBJECT": mapped_subject,
                "CLASS": class_name,
                "METHOD": method_name,
                "MODEL": model_id,
                "SPECFUZZER_SPECS_PRE-BUCKET": specs_pre_bucket,
                "SPECFUZZER_SPECS_POST-BUCKET": specs_post_bucket,
                "TESTS_GENERATED_BY_LLM": raw_tests,
                "TESTS_COMPILED": compiled_tests,
                "NEW_SPECS_FILTERED_PRE-BUCKET": new_specs_filtered,
                "NEW_SPECS_POST-BUCKET": new_specs_post_bucket,
            }
            unified_results.append(unified_result)

    if unified_results:
        # Create results directory if it doesn't exist
        os.makedirs("experiments/results", exist_ok=True)

        # Write main results file (single comprehensive output)
        main_csv_file = "experiments/results/llm_test_generation_results.csv"
        with open(main_csv_file, "w", newline="") as f:
            fieldnames = [
                "SUBJECT",
                "CLASS",
                "METHOD",
                "MODEL",
                "SPECFUZZER_SPECS_PRE-BUCKET",
                "SPECFUZZER_SPECS_POST-BUCKET",
                "TESTS_GENERATED_BY_LLM",
                "TESTS_COMPILED",
                "NEW_SPECS_FILTERED_PRE-BUCKET",
                "NEW_SPECS_POST-BUCKET",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(unified_results)

        # Generate best performing models summary
        best_models = get_best_performing_models(unified_results)
        best_models_file = "experiments/results/best_performing_models.csv"

        # Generate best model per subject summary
        subject_best_models = get_best_model_per_subject(
            unified_results, subjects_order
        )
        subject_summary_file = "experiments/results/best_model_per_subject.csv"

        if best_models:
            with open(best_models_file, "w", newline="") as f:
                fieldnames = [
                    "MODEL",
                    "SUBJECTS",
                    "GENERATED",
                    "COMPILED",
                    "NEW_SPECS_FILTERED",
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(best_models)

            print(f"Best performing models summary written to {best_models_file}")

        if subject_best_models:
            with open(subject_summary_file, "w", newline="") as f:
                fieldnames = [
                    "SUBJECT",
                    "CLASS",
                    "METHOD",
                    "BEST_MODEL",
                    "SPECFUZZER_SPECS_PRE-BUCKET",
                    "SPECFUZZER_SPECS_POST-BUCKET",
                    "TESTS_GENERATED_BY_LLM",
                    "TESTS_COMPILED",
                    "NEW_SPECS_FILTERED_PRE-BUCKET",
                    "NEW_SPECS_POST-BUCKET",
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(subject_best_models)

            print(f"Best model per subject summary written to {subject_summary_file}")

        print(f"Comprehensive results written to {main_csv_file}")

        # Display summary following priority order
        print("\n" + "=" * 80)
        print("LLM TEST GENERATION ANALYSIS SUMMARY")
        print("Priority: Specifications Filtered > Generated → Compiled Tests")
        print("=" * 80)

        total_subjects = len(set(r["SUBJECT"] for r in unified_results))
        total_models = len(set(r["MODEL"] for r in unified_results))
        print(f"Subjects evaluated: {total_subjects}")
        print(f"Models evaluated: {total_models}")
        print(f"Total experimental configurations: {len(unified_results)}")

        # Aggregate statistics
        total_generated = sum(r["TESTS_GENERATED_BY_LLM"] for r in unified_results)
        total_compiled = sum(r["TESTS_COMPILED"] for r in unified_results)
        total_specs_filtered = sum(
            r["NEW_SPECS_FILTERED_PRE-BUCKET"] for r in unified_results
        )

        print("\nAGGREGATE RESULTS:")
        print(f"  Specifications Filtered: {total_specs_filtered}")
        print(f"  Tests Generated: {total_generated}")
        print(f"  Tests Compiled: {total_compiled}")

        # Calculate overall rates
        if total_generated > 0:
            overall_success_rate = total_compiled / total_generated * 100
        else:
            overall_success_rate = 0

        print("\nTEST SUCCESS RATES (Generated → Compiled):")
        print(f"  Success Rate: {overall_success_rate:.2f}%")

        # Show top 3 performing models by specs filtered
        print("\nTOP PERFORMING MODELS (by Specifications Filtered):")
        for i, model in enumerate(best_models[:3], 1):
            gen = model["GENERATED"]
            comp = model["COMPILED"]
            comp_rate = (comp / gen * 100) if gen > 0 else 0
            print(
                f"  {i}. {model['MODEL']}: {model['NEW_SPECS_FILTERED']} specs, "
                f"{gen}→{comp} tests "
                f"({comp_rate:.1f}% success)"
            )

        # Show best model per subject
        print("\nBEST MODEL PER SUBJECT (by Specifications Filtered):")
        for subject_info in subject_best_models:
            gen = subject_info["TESTS_GENERATED_BY_LLM"]
            comp = subject_info["TESTS_COMPILED"]
            comp_rate = (comp / gen * 100) if gen > 0 else 0
            print(
                f"  {subject_info['SUBJECT']}: {subject_info['BEST_MODEL']} "
                f"({subject_info['NEW_SPECS_FILTERED_PRE-BUCKET']} specs, "
                f"{gen}→{comp} tests, {comp_rate:.1f}% success)"
            )

        print(f"\nDetailed results available in: {main_csv_file}")
        if best_models:
            print(f"Model rankings available in: {best_models_file}")
        if subject_best_models:
            print(f"Best model per subject available in: {subject_summary_file}")

    else:
        print(
            "No results found - check that output directory contains processed subjects"
        )


if __name__ == "__main__":
    main()
