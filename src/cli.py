from argsparser.parser import build_parser
from core import Core
from llmservice.llm_service import LLMService
from prompt.prompt_template import PromptID


def print_available_llms(llm_service: LLMService):
    models = llm_service.get_all_models()
    print("📋 Available LLMs:")
    print("=" * 40)

    local_models = [m for m in models if m.startswith("L_")]
    remote_models = [m for m in models if not m.startswith("L_")]

    if local_models:
        print("\n🖥️  Local Models:")
        for i, model in enumerate(sorted(local_models), 1):
            model_url = llm_service.get_model_url(model)
            print(f"  {i:2d}. {model}")
            if model_url != model:
                print(f"      → {model_url}")

    if remote_models:
        print("\n☁️  Remote Models:")
        for i, model in enumerate(sorted(remote_models), 1):
            model_url = llm_service.get_model_url(model)
            print(f"  {i:2d}. {model}")
            if model_url != model:
                print(f"      → {model_url}")

    print(f"\nTotal: {len(models)} models available")


def print_available_prompts():
    prompts = list(PromptID)
    print("💬 Available Prompts:")
    print("=" * 40)

    for i, prompt in enumerate(prompts, 1):
        print(f"  {i}. {prompt.name}")
        print(f"     Value: {prompt.value}")

    print(f"\nTotal: {len(prompts)} prompts available")


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.list_llms:
        llm_service = LLMService()
        print_available_llms(llm_service)
        return

    if args.list_prompts:
        print_available_prompts()
        return

    # Check if a command was provided
    if not args.command:
        parser.error(
            "the following arguments are required: command "
            "(unless using --list-llms or --list-prompts)"
        )

    # Validation for testgen command
    if args.command == "testgen":
        if not args.no_invs_filtering and not args.specfuzzer_invs_file:
            print(
                "Error: specfuzzer .inv.gz file is required when "
                "not using --no-invs-filtering"
            )
            return
        if not args.no_invs_filtering and not args.specfuzzer_assertions_file:
            print(
                "Error: specfuzzer .assertions file is required when "
                "not using --no-invs-filtering"
            )
            return

    core = Core(args)
    print(f"> Running Specvalid for subject: {core.subject_id}")
    if args.command == "testgen":
        print("> Running test generation")
        core.run_testgen(args)
        if args.no_invs_filtering:
            print("> Second validation skipped due to --no-invs-filtering flag")
        else:
            core.run_invariant_filter()
        print("> Done ✅")
    elif args.command == "mutgen":
        raise NotImplementedError("Mutgen functionality is not implemented yet.")
    elif args.command == "verify-only":
        print("> Running verification only")
        core.run_verification_only()
        print("> Done ✅")
    else:
        print(f"Error: Unknown command '{args.command}'")
        return
