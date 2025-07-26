

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="specvalid")
    sub = parser.add_subparsers(dest="command", required=True)

    # testgen command
    testgen = sub.add_parser("testgen")
    testgen.add_argument("target_class_src")
    testgen.add_argument("test_suite")
    testgen.add_argument("assertions_file")
    testgen.add_argument("method")

    # mutgen command (placeholder)
    sub.add_parser("mutgen")

    return parser
