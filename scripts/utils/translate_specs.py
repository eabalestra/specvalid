#!/usr/bin/env python3
"""
Script to translate specs from a buckets.assertions file to human-readable format.

Usage:
    python scripts/translate_specs.py <buckets_file> [--class-src <path>] [--method <name>]

Example:
    python scripts/translate_specs.py output/SimpleMethods_abs/bucketing/model_GPT51/SimpleMethods-abs-GPT51-specvalid-buckets.assertions
"""

import argparse
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from specs.specs import Specs


def extract_info_from_filename(filename: str) -> tuple:
    """
    Extract class name and method name from the filename.
    Expected format: ClassName-methodName-*-specvalid-buckets.assertions
    """
    basename = os.path.basename(filename)
    # Remove extension
    name = basename.replace("-specvalid-buckets.assertions", "")
    name = name.replace("-specvalid.assertions", "")

    # Split by dash to get parts
    parts = name.split("-")
    if len(parts) >= 2:
        class_name = parts[0]
        method_name = parts[1]
        return class_name, method_name

    return "", ""


def translate_specs(
    buckets_file: str, class_src: str = None, method_name: str = None
) -> list:
    """
    Translate specs from a buckets.assertions file.

    Args:
        buckets_file: Path to the buckets.assertions file
        class_src: Optional path to the Java class source file
        method_name: Optional method name

    Returns:
        List of tuples (original_spec, translated_spec)
    """
    # Extract info from filename if not provided
    if not class_src or not method_name:
        extracted_class, extracted_method = extract_info_from_filename(buckets_file)
        if not class_src:
            class_src = f"{extracted_class}.java"
        if not method_name:
            method_name = extracted_method

    # Create Specs instance
    specs = Specs(buckets_file, class_src, method_name)

    # Parse specs
    raw_specs = specs.parse_and_collect_specs()

    # Translate each spec
    translations = []
    for spec in sorted(raw_specs):
        if spec.strip():  # Skip empty lines
            translated = specs.transform_specification_vars(spec)
            translations.append((spec, translated))

    return translations


def main():
    parser = argparse.ArgumentParser(
        description="Translate specs from a buckets.assertions file"
    )
    parser.add_argument("buckets_file", help="Path to the buckets.assertions file")
    parser.add_argument(
        "--class-src",
        help="Path to the Java class source file (optional, extracted from filename)",
    )
    parser.add_argument(
        "--method", help="Method name (optional, extracted from filename)"
    )
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    parser.add_argument(
        "--format",
        "-f",
        choices=["simple", "full", "csv"],
        default="simple",
        help="Output format: simple (translated only), full (original -> translated), csv",
    )

    args = parser.parse_args()

    if not os.path.exists(args.buckets_file):
        print(f"Error: File not found: {args.buckets_file}", file=sys.stderr)
        sys.exit(1)

    translations = translate_specs(args.buckets_file, args.class_src, args.method)

    # Format output
    output_lines = []

    if args.format == "simple":
        for _, translated in translations:
            output_lines.append(translated)
    elif args.format == "full":
        for original, translated in translations:
            output_lines.append(f"{original}")
            output_lines.append(f"  -> {translated}")
            output_lines.append("")
    elif args.format == "csv":
        output_lines.append("original,translated")
        for original, translated in translations:
            # Escape quotes for CSV
            orig_escaped = original.replace('"', '""')
            trans_escaped = translated.replace('"', '""')
            output_lines.append(f'"{orig_escaped}","{trans_escaped}"')

    output_text = "\n".join(output_lines)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output_text)
        print(f"Translations written to: {args.output}")
    else:
        print(output_text)

    print(f"\nTotal specs translated: {len(translations)}", file=sys.stderr)


if __name__ == "__main__":
    main()
