import argparse

from core import run_testgen


def main():
    parser = argparse.ArgumentParser(prog="specvalid")
    sub = parser.add_subparsers(dest="command", required=True)

    # ./run-automatic-invariant-filtering.sh
    # QueueAr_makeEmpty DataStructures.QueueAr makeEmpty
    # -m "Llama323Instruct" -p "General_V1"
    testgen = sub.add_parser("testgen")
    testgen.add_argument("target_classpath")
    testgen.add_argument("target_class")
    testgen.add_argument("target_class_src")
    testgen.add_argument("test_suite")
    testgen.add_argument("method")

    mutgen = sub.add_parser("mutgen")

    args = parser.parse_args()

    if args.command == "testgen":
        run_testgen()
    if args.command == "mutgen":
        raise NotImplementedError(
            "Mutgen functionality is not implemented yet.")
