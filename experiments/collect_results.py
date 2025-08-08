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

    # Handle naming variations
    for existing_subject in existing_subjects:
        if existing_subject not in name_mapping:
            # Try to find a match by method name
            existing_parts = existing_subject.split("_")
            if len(existing_parts) > 1:
                existing_method = existing_parts[-1]
            else:
                existing_method = existing_subject

            for mapped_subject, (class_name, method_name) in subjects_map.items():
                if method_name == existing_method:
                    mapping_info = (mapped_subject, (class_name, method_name))
                    name_mapping[existing_subject] = mapping_info
                    break

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


def main():
    # Base output directory
    base_dir = "output"
    subjects_file = "experiments/subjects"

    # Load subject mapping and order
    subjects_map, subjects_order = load_subject_mapping(subjects_file)

    # List to store results
    results = []

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

    # Process subjects in order
    for subject in ordered_existing_subjects:
        # Get class and method names from mapping
        if subject in name_mapping:
            mapped_subject, (class_name, method_name) = name_mapping[subject]
        else:
            mapped_subject, class_name, method_name = subject, "", ""

        # Paths to the log files in new structure
        testgen_log_file = os.path.join(base_dir, subject, "logs", "testgen.log")
        invfilter_log_file = os.path.join(base_dir, subject, "logs", "invfilter.log")

        result = {
            "SUBJECT": mapped_subject,  # Use the mapped name for display
            "CLASS": class_name,
            "METHOD": method_name,
            "generated-tests": 0,
            "compiled-tests": 0,
            "specs-in-dot-assertions": 0,
            "new-specs-filtered": 0,
        }

        # Extract test generation stats
        if os.path.exists(testgen_log_file):
            generated, compiled = extract_test_counts(testgen_log_file)
            result["generated-tests"] = generated
            result["compiled-tests"] = compiled
        else:
            print(f"Test generation log not found for {subject}")

        # Extract invariant filtering stats
        if os.path.exists(invfilter_log_file):
            specs_in_buckets, filtered_specs = extract_spec_counts(invfilter_log_file)
            result["specs-in-dot-assertions"] = specs_in_buckets
            result["new-specs-filtered"] = filtered_specs
        else:
            print(f"Invariant filter log not found for {subject}")

        # Add the result
        results.append(result)

    if results:
        # Create results directory if it doesn't exist
        os.makedirs("experiments/results", exist_ok=True)

        # Write results to CSV
        csv_file = "experiments/results/test_generation_stats.csv"
        with open(csv_file, "w", newline="") as f:
            fieldnames = [
                "SUBJECT",
                "CLASS",
                "METHOD",
                "generated-tests",
                "compiled-tests",
                "specs-in-dot-assertions",
                "new-specs-filtered",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

        print(f"Results written to {csv_file}")
        print("\nSummary:")
        print(f"Total subjects processed: {len(results)}")
        total_generated = sum(r["generated-tests"] for r in results)
        total_compiled = sum(r["compiled-tests"] for r in results)
        print(f"Total generated tests: {total_generated}")
        print(f"Total compiled tests: {total_compiled}")

        if total_generated > 0:
            compilation_rate = (total_compiled / total_generated) * 100
            print(f"Average compilation rate: {compilation_rate:.2f}%")
        else:
            print("Average compilation rate: 0.00% (no tests generated)")

        total_specs_buckets = sum(r["specs-in-dot-assertions"] for r in results)
        total_filtered = sum(r["new-specs-filtered"] for r in results)
        print(f"Total specs in buckets: {total_specs_buckets}")
        print(f"Total new specs filtered: {total_filtered}")
    else:
        print("No results found")


if __name__ == "__main__":
    main()
