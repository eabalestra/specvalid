from argsparser.parser import build_parser
from core import run_testgen
from java_test_preparer.java_test_preparer import JavaTestPreparer
from llmservice.llm_service import LLMService
from prompt.prompt_id import PromptID


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.list_llms:
        llm_service = LLMService()
        print("Supported LLMs:", llm_service.get_all_models(), sep="\n")
        return
    if args.list_prompts:
        print("Available PromptIDs:", *[p.name for p in PromptID], sep="\n")
        return

    if args.command == "testgen":
        # Run test generation using LLM's
        run_testgen(args)
        # Prepare the augmented test files (old tests + generated tests)
        new_test_suite = JavaTestPreparer.prepare_test_file(
            args.test_suite, "Augmented", is_driver=False
        )
        new_test_driver = JavaTestPreparer.prepare_test_file(
            args.test_driver, "Augmented", is_driver=True
        )
        # run fix generated test files
        # run discard uncompilable test files
        # run append test files to the destination
    elif args.command == "mutgen":
        raise NotImplementedError("Mutgen functionality is not implemented yet.")
