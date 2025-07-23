import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--testgen", action="store_true",
                        help="Generate tests for the project")

    args = parser.parse_args()

    if args.testgen:
        raise NotImplementedError("Test generation is not implemented yet.")
