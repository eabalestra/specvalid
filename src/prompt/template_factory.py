from prompt.prompt_template import Prompt, PromptID

from prompt.templates.compilation_fix.compilation_fix_prompt import CompilationFixPrompt
from prompt.templates.test_generation.general.general_prompt import GeneralPrompt


class PromptTemplateFactory:
    @staticmethod
    def create_prompt(prompt_id, class_code, method_code, spec) -> Prompt:
        if prompt_id == PromptID.General_V1:
            return GeneralPrompt(PromptID.General_V1, class_code, method_code, spec)
        if prompt_id == PromptID.NOT_COMPILABLE:
            return CompilationFixPrompt(
                PromptID.NOT_COMPILABLE, class_code, method_code, spec
            )
        raise ValueError(f"Unknown prompt ID: {prompt_id}")
