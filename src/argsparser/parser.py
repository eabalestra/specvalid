import argparse


def list_of_strings(arg):
    return arg.split(",")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="specvalid")
    sub = parser.add_subparsers(dest="command", required=True)

    # testgen command
    testgen = sub.add_parser("testgen")
    testgen.add_argument(
        "--no-invs-filtering",
        dest="no_invs_filtering",
        action="store_true",
        help="Skip the Daikon invariants filtering step.",
        required=False,
    )
    testgen.add_argument("target_class_src")
    testgen.add_argument("test_suite")
    testgen.add_argument("test_driver")
    testgen.add_argument("assertions_file")
    testgen.add_argument("method")
    testgen.add_argument(
        "-m",
        "--models",
        type=list_of_strings,
        dest="models_list",
        default="",
        help="List the LLMs to run.",
        metavar="MODELS",
    )
    testgen.add_argument(
        "-sw",
        "--starts-with",
        type=str,
        dest="models_prefix",
        default=None,
        help="Selects all LLMs starting with the <prefix>.",
        metavar="PREFIX",
    )
    testgen.add_argument(
        "-p",
        "--prompts",
        type=list_of_strings,
        dest="prompts_list",
        default="",
        help="List the prompts to use.",
        metavar="PROMPTS",
    )
    testgen.add_argument(
        "-ll",
        "--llms",
        "--llm-list",
        dest="list_llms",
        action="store_true",
        help="List the supported LLMs.",
    )
    testgen.add_argument(
        "-pl",
        "--prompt-list",
        dest="list_prompts",
        action="store_true",
        help="List the available prompts.",
    )
    testgen.add_argument(
        "-sf",
        "--specfuzzer-invs",
        dest="specfuzzer_invs_file",
        help="Path to the specfuzzer <file>.inv.gz file. ",
        required=False,
    )
    testgen.add_argument(
        "-sa",
        "--specfuzzer-assertions",
        dest="specfuzzer_assertions_file",
        help="Path to the specfuzzer <file>.assertions file. ",
        required=False,
    )

    # mutgen command (placeholder)
    sub.add_parser("mutgen")
    return parser
