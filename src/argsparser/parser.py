import argparse


def list_of_strings(arg):
    return arg.split(",")


def _add_shared_subject_args(command_parser: argparse.ArgumentParser) -> None:
    command_parser.add_argument("target_class_src")
    command_parser.add_argument("test_suite")
    command_parser.add_argument("test_driver")
    command_parser.add_argument("buckets_assertions_file")
    command_parser.add_argument("method")
    command_parser.add_argument(
        "-m",
        "--models",
        type=list_of_strings,
        dest="models_list",
        default="",
        help="List the LLMs to run.",
        metavar="MODELS",
    )
    command_parser.add_argument(
        "-sw",
        "--starts-with",
        type=str,
        dest="models_prefix",
        default=None,
        help="Selects all LLMs starting with the <prefix>.",
        metavar="PREFIX",
    )
    command_parser.add_argument(
        "-p",
        "--prompts",
        type=list_of_strings,
        dest="prompts_list",
        default="",
        help="List the prompts to use.",
        metavar="PROMPTS",
    )
    command_parser.add_argument(
        "-sf",
        "--specfuzzer-invs",
        dest="specfuzzer_invs_file",
        help="Path to the specfuzzer <file>.inv.gz file. ",
        required=False,
    )
    command_parser.add_argument(
        "-sa",
        "--specfuzzer-assertions",
        dest="specfuzzer_assertions_file",
        help="Path to the specfuzzer <file>.assertions file. ",
        required=False,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="specvalid")

    parser.add_argument(
        "--list-llms",
        dest="list_llms",
        action="store_true",
        help="List all supported LLMs and exit.",
    )
    parser.add_argument(
        "--list-prompts",
        dest="list_prompts",
        action="store_true",
        help="List all available prompts and exit.",
    )
    parser.add_argument(
        "--output-dir",
        dest="output_dir",
        type=str,
        default="output",
        help="Directory where all output files will be stored (default: output).",
        metavar="PATH",
    )

    sub = parser.add_subparsers(dest="command", required=False)

    # testgen command
    testgen = sub.add_parser("testgen")
    testgen.add_argument(
        "--no-invs-filtering",
        dest="no_invs_filtering",
        action="store_true",
        help="Skip the Daikon invariants filtering step.",
        required=False,
    )
    testgen.add_argument(
        "--reuse-tests",
        dest="reuse_tests",
        action="store_true",
        help="Reuse existing raw tests if available instead of generating new ones.",
        required=False,
    )
    _add_shared_subject_args(testgen)

    # mutgen command (placeholder)
    sub.add_parser("mutgen")

    # verification only command
    verification_only = sub.add_parser("verify-only")
    _add_shared_subject_args(verification_only)

    return parser
