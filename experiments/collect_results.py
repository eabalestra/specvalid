import os
import re
import csv


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
    """
    generated_tests = 0
    compiled_tests = 0

    try:
        with open(log_file, "r") as f:
            content = f.read()

            # Find the number of generated tests - updated pattern
            gen_match = re.search(r"Processing (\d+) tests for", content)
            if gen_match:
                generated_tests = int(gen_match.group(1))

            # Find the number of compiled tests
            comp_match = re.search(r"Compiled (\d+) tests successfully", content)
            if comp_match:
                compiled_tests = int(comp_match.group(1))

        return generated_tests, compiled_tests

    except Exception as e:
        print(f"Error processing {log_file}: {str(e)}")
        return 0, 0


def extract_spec_counts(invfilter_log_file):
    """
    Extract the number of specifications from invfilter.log.
    """
    specs_in_buckets = 0
    filtered_specs = 0

    try:
        with open(invfilter_log_file, "r") as f:
            content = f.read()

            # Find the number of original specs
            buckets_match = re.search(r"Specs from .*\.assertions: (\d+)", content)
            if buckets_match:
                specs_in_buckets = int(buckets_match.group(1))

            # Find the number of filtered specs
            filtered_match = re.search(r"Filtered specs: (\d+)", content)
            if filtered_match:
                filtered_specs = int(filtered_match.group(1))

        return specs_in_buckets, filtered_specs

    except Exception as e:
        print(f"Error processing {invfilter_log_file}: {str(e)}")
        return 0, 0


def extract_model_stats(model_output_dir):
    """
    Extract statistics for individual models from their directories.
    Returns dict with model stats: {model_id: stats}
    """
    model_stats = {}
    by_model_dir = os.path.join(model_output_dir, "by_model")

    if not os.path.exists(by_model_dir):
        return model_stats

    # Read invfilter.log to get specs counts per model
    invfilter_log = os.path.join(
        os.path.dirname(model_output_dir), "logs", "invfilter.log"
    )
    specs_counts_by_model = {}

    if os.path.exists(invfilter_log):
        try:
            with open(invfilter_log, "r") as f:
                content = f.read()

                # Find all sections for each model
                import re

                # Look for model-specific filtering sections
                lines = content.split("\n")
                current_model = None

                for line in lines:
                    # Look for model directory references to identify which model
                    if "by_model/" in line and "specs/interest-specs.csv" in line:
                        model_match = re.search(r"by_model/([^/]+)/specs", line)
                        if model_match:
                            current_model = model_match.group(1)

                    # Look for filtered specs count
                    if current_model and line.strip().startswith("Filtered specs:"):
                        specs_match = re.search(r"Filtered specs: (\d+)", line)
                        if specs_match:
                            filtered_count = int(specs_match.group(1))
                            if current_model not in specs_counts_by_model:
                                specs_counts_by_model[current_model] = filtered_count
                            current_model = None  # Reset after finding the count

        except Exception as e:
            print(f"Error reading invfilter.log: {e}")

    for model_name in os.listdir(by_model_dir):
        model_dir = os.path.join(by_model_dir, model_name)
        if not os.path.isdir(model_dir):
            continue

        stats = {
            "raw_tests": 0,
            "compiled_tests": 0,
            "fixed_tests": 0,
            "specs_in_buckets": 0,
            "filtered_specs": 0,
        }

        # Read metadata files for test counts
        for phase in ["raw", "compiled", "fixed"]:
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
                        elif phase == "fixed":
                            stats["fixed_tests"] = test_count
                except Exception as e:
                    print(f"Error reading {metadata_file}: {e}")

        # Use specs count from invfilter.log if available
        if model_name in specs_counts_by_model:
            stats["filtered_specs"] = specs_counts_by_model[model_name]
        else:
            # Fallback: Read specs from model-specific directory
            model_specs_dir = os.path.join(model_dir, "specs")
            if os.path.exists(model_specs_dir):
                specs_file = os.path.join(model_specs_dir, "interest-specs.csv")
                if os.path.exists(specs_file):
                    try:
                        with open(specs_file, "r") as f:
                            lines = f.readlines()
                            # Count non-header lines
                            specs_count = max(0, len(lines) - 1)
                            stats["filtered_specs"] = specs_count
                    except Exception as e:
                        print(f"Error reading {specs_file}: {e}")

        model_stats[model_name] = stats

    return model_stats


def calculate_success_rates(stats):
    """Calculate success rates following the priority: generated -> fixed -> compiled"""
    generated = stats.get("raw_tests", 0)
    fixed = stats.get("fixed_tests", 0)
    compiled = stats.get("compiled_tests", 0)

    # Primary metric: Generation to Fix rate (most important)
    gen_to_fix_rate = (fixed / generated * 100) if generated > 0 else 0.0

    # Secondary metric: Fix to Compilation rate
    fix_to_comp_rate = (compiled / fixed * 100) if fixed > 0 else 0.0

    # Overall end-to-end rate (for reference)
    overall_rate = (compiled / generated * 100) if generated > 0 else 0.0

    return gen_to_fix_rate, fix_to_comp_rate, overall_rate


def get_best_performing_models(model_results):
    """Identify best performing models by specs filtered, then test success rates"""
    model_performance = {}

    for result in model_results:
        model = result["MODEL"]
        if model not in model_performance:
            model_performance[model] = {
                "subjects": [],
                "total_generated": 0,
                "total_fixed": 0,
                "total_compiled": 0,
                "total_specs": 0,
            }

        perf = model_performance[model]
        perf["subjects"].append(result["SUBJECT"])
        perf["total_generated"] += result["TESTS_GENERATED"]
        perf["total_fixed"] += result["TESTS_FIXED"]
        perf["total_compiled"] += result["TESTS_COMPILED"]
        perf["total_specs"] += result["SPECS_FILTERED"]

    # Calculate aggregate rates for each model
    best_models = []
    for model, perf in model_performance.items():
        best_models.append(
            {
                "MODEL": model,
                "SUBJECTS": len(perf["subjects"]),
                "GENERATED": perf["total_generated"],
                "FIXED": perf["total_fixed"],
                "COMPILED": perf["total_compiled"],
                "SPECS_FILTERED": perf["total_specs"],
            }
        )

    # Sort by specifications filtered first, then by tests compiled
    best_models.sort(
        key=lambda x: (x["SPECS_FILTERED"], x["COMPILED"], x["FIXED"]), reverse=True
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
            # Sort by specs filtered first, then by tests compiled, then fixed
            best_result = max(
                results,
                key=lambda x: (
                    x["SPECS_FILTERED"],
                    x["TESTS_COMPILED"],
                    x["TESTS_FIXED"],
                ),
            )

            subject_best_models.append(
                {
                    "SUBJECT": subject,
                    "CLASS": best_result["CLASS"],
                    "METHOD": best_result["METHOD"],
                    "BEST_MODEL": best_result["MODEL"],
                    "SPECS_AVAILABLE": best_result["SPECS_AVAILABLE"],
                    "TESTS_GENERATED": best_result["TESTS_GENERATED"],
                    "TESTS_FIXED": best_result["TESTS_FIXED"],
                    "TESTS_COMPILED": best_result["TESTS_COMPILED"],
                    "SPECS_FILTERED": best_result["SPECS_FILTERED"],
                }
            )

    # Add any remaining subjects that weren't in the subjects file
    for subject, results in subjects_summary.items():
        if subject not in subjects_order:
            best_result = max(
                results,
                key=lambda x: (
                    x["SPECS_FILTERED"],
                    x["TESTS_COMPILED"],
                    x["TESTS_FIXED"],
                ),
            )

            subject_best_models.append(
                {
                    "SUBJECT": subject,
                    "CLASS": best_result["CLASS"],
                    "METHOD": best_result["METHOD"],
                    "BEST_MODEL": best_result["MODEL"],
                    "SPECS_AVAILABLE": best_result["SPECS_AVAILABLE"],
                    "TESTS_GENERATED": best_result["TESTS_GENERATED"],
                    "TESTS_FIXED": best_result["TESTS_FIXED"],
                    "TESTS_COMPILED": best_result["TESTS_COMPILED"],
                    "SPECS_FILTERED": best_result["SPECS_FILTERED"],
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

        # Paths to the log files in new structure
        invfilter_log_file = os.path.join(base_dir, subject, "logs", "invfilter.log")
        test_output_dir = os.path.join(base_dir, subject, "test")

        # Extract specifications stats (consistent across all models for a subject)
        specs_in_buckets, filtered_specs = 0, 0
        if os.path.exists(invfilter_log_file):
            specs_in_buckets, filtered_specs = extract_spec_counts(invfilter_log_file)

        # Extract model-specific statistics
        model_stats = extract_model_stats(test_output_dir)

        # Create unified results with proper priority ordering
        for model_id, stats in model_stats.items():
            rates = calculate_success_rates(stats)
            gen_to_fix_rate, fix_to_comp_rate, overall_rate = rates

            unified_result = {
                "SUBJECT": mapped_subject,
                "CLASS": class_name,
                "METHOD": method_name,
                "MODEL": model_id,
                "SPECS_AVAILABLE": specs_in_buckets,
                "TESTS_GENERATED": stats["raw_tests"],
                "TESTS_FIXED": stats["fixed_tests"],
                "TESTS_COMPILED": stats["compiled_tests"],
                "SPECS_FILTERED": stats["filtered_specs"],
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
                "SPECS_AVAILABLE",
                "TESTS_GENERATED",
                "TESTS_FIXED",
                "TESTS_COMPILED",
                "SPECS_FILTERED",
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
                    "FIXED",
                    "COMPILED",
                    "SPECS_FILTERED",
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
                    "SPECS_AVAILABLE",
                    "TESTS_GENERATED",
                    "TESTS_FIXED",
                    "TESTS_COMPILED",
                    "SPECS_FILTERED",
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(subject_best_models)

            print(f"Best model per subject summary written to {subject_summary_file}")

        print(f"Comprehensive results written to {main_csv_file}")

        # Display summary following priority order
        print("\n" + "=" * 80)
        print("LLM TEST GENERATION ANALYSIS SUMMARY")
        print("Priority: Specifications Filtered > Generated → Fixed → Compiled Tests")
        print("=" * 80)

        total_subjects = len(set(r["SUBJECT"] for r in unified_results))
        total_models = len(set(r["MODEL"] for r in unified_results))
        print(f"Subjects evaluated: {total_subjects}")
        print(f"Models evaluated: {total_models}")
        print(f"Total experimental configurations: {len(unified_results)}")

        # Aggregate statistics
        total_generated = sum(r["TESTS_GENERATED"] for r in unified_results)
        total_fixed = sum(r["TESTS_FIXED"] for r in unified_results)
        total_compiled = sum(r["TESTS_COMPILED"] for r in unified_results)
        total_specs = sum(r["SPECS_FILTERED"] for r in unified_results)

        print("\nAGGREGATE RESULTS:")
        print(f"  Specifications Filtered: {total_specs}")
        print(f"  Tests Generated: {total_generated}")
        print(f"  Tests Fixed: {total_fixed}")
        print(f"  Tests Compiled: {total_compiled}")

        # Calculate overall rates
        if total_generated > 0:
            overall_gen_to_fix = total_fixed / total_generated * 100
        else:
            overall_gen_to_fix = 0

        if total_fixed > 0:
            overall_fix_to_comp = total_compiled / total_fixed * 100
        else:
            overall_fix_to_comp = 0

        if total_generated > 0:
            overall_end_to_end = total_compiled / total_generated * 100
        else:
            overall_end_to_end = 0

        print("\nTEST SUCCESS RATES (Generated → Fixed → Compiled):")
        print(f"  1. Generation → Fix Rate: {overall_gen_to_fix:.2f}%")
        print(f"  2. Fix → Compilation Rate: {overall_fix_to_comp:.2f}%")
        print(f"  3. End-to-End Success Rate: {overall_end_to_end:.2f}%")

        # Show top 3 performing models by specs filtered
        print("\nTOP PERFORMING MODELS (by Specifications Filtered):")
        for i, model in enumerate(best_models[:3], 1):
            gen = model["GENERATED"]
            comp = model["COMPILED"]
            comp_rate = (comp / gen * 100) if gen > 0 else 0
            print(
                f"  {i}. {model['MODEL']}: {model['SPECS_FILTERED']} specs, "
                f"{gen}→{model['FIXED']}→{comp} tests "
                f"({comp_rate:.1f}% success)"
            )

        # Show best model per subject
        print("\nBEST MODEL PER SUBJECT (by Specifications Filtered):")
        for subject_info in subject_best_models:
            gen = subject_info["TESTS_GENERATED"]
            fix = subject_info["TESTS_FIXED"]
            comp = subject_info["TESTS_COMPILED"]
            comp_rate = (comp / gen * 100) if gen > 0 else 0
            print(
                f"  {subject_info['SUBJECT']}: {subject_info['BEST_MODEL']} "
                f"({subject_info['SPECS_FILTERED']} specs, "
                f"{gen}→{fix}→{comp} tests, {comp_rate:.1f}% success)"
            )

        print(f"\nDetailed results available in: {main_csv_file}")
        if best_models:
            print(f"Model rankings available in: {best_models_file}")
        if subject_best_models:
            print(f"Best model per subject available in: {subject_summary_file}")

    else:
        print(
            "No results found - check that output directory contains "
            "processed subjects"
        )


if __name__ == "__main__":
    main()
