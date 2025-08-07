from argsparser.parser import build_parser
from core import run_invariant_filtering, run_testgen
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
    if not args.no_invs_filtering and not args.specfuzzer_invs_file:
        print(
            "Error: specfuzzer .inv.gz file is required when \
            not using --no-invs-filtering"
        )
        return
    if not args.no_invs_filtering and not args.specfuzzer_assertions_file:
        print(
            "Error: specfuzzer .assertions file is required when \
            not using --no-invs-filtering"
        )
        return

    if args.command == "testgen":
        run_testgen(args)
        if args.no_invs_filtering:
            print("> Second validation skipped due to --no-invs-filtering flag")
        else:
            print("> Running filtering")
            run_invariant_filtering(args)
    elif args.command == "mutgen":
        raise NotImplementedError("Mutgen functionality is not implemented yet.")

    print("> Done ✅")
