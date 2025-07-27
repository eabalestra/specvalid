from argsparser.parser import build_parser
from core import run_testgen
from llmservice.llm_service import LLMService
from prompt.prompt_id import PromptID


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.list_llms:
        llm_service = LLMService()
        print("Supported LLMs:", llm_service.get_all_models(), sep='\n')
        return
    if args.list_prompts:
        print("Available PromptIDs:", *[p.name for p in PromptID], sep='\n')
        return

    if args.command == "testgen":
        run_testgen(args)
    elif args.command == "mutgen":
        raise NotImplementedError(
            "Mutgen functionality is not implemented yet.")
