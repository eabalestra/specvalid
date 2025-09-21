import os
import sys
import pandas as pd

specfuzzer_assertions_file = sys.argv[1]
invalid_post_conditions_csv = sys.argv[2]

# Read SpecFuzzer assertions file
with open(specfuzzer_assertions_file, "r") as file:
    set1 = {line.strip() for line in file}

set1 = {
    item
    for item in set1
    if item
    and not item.startswith(
        "==========================================================================="
    )
    and ":::OBJECT" not in item
    and ":::ENTER" not in item
    and ":::EXIT" not in item
}

# Read CSV file with post-conditions that Daikon considered invalid
df = pd.read_csv(invalid_post_conditions_csv)
set2 = set(df["invariant"].str.strip())

# The specs that were filtered are those that are in both sets
filtered_specs = set1 & set2

# Find difference
difference = set1 - set2

assertions_file_name = os.path.basename(specfuzzer_assertions_file)
print(f"Specs from {assertions_file_name}: {len(set1)}")
print(f"Filtered specs: {len(filtered_specs)}")
for spec in sorted(filtered_specs):
    print(f"  {spec}")

# Write remaining specifications to output file
if len(sys.argv) > 3:
    class_name = sys.argv[3]
    method_name = sys.argv[4]
    output_directory = sys.argv[5]

    os.makedirs(output_directory, exist_ok=True)

    output_file = (
        f"{output_directory}/{class_name}-{method_name}-specfuzzer-refined.assertions"
    )

    difference = sorted(difference, reverse=True)
    with open(output_file, "w") as file:
        for item in difference:
            file.write(f"{item}\n")
