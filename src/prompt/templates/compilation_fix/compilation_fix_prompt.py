from prompt.prompt_template import Prompt


class CompilationFixPrompt(Prompt):
    def generate_prompt(self) -> str:
        NOT_COMPILABLE_PROMPT_TEMPLATE = """
Fix the previously generated code to resolve compilation issues.

- Original LLM response + compilation errors:
{llm_response}

- Class under test (do not modify):
{class_code}

- Method under test:
{method_code}
"""
        formatted_prompt = NOT_COMPILABLE_PROMPT_TEMPLATE.format(
            llm_response=self.spec,
            class_code=self.class_code,
            method_code=self.method_code,
        )
        return formatted_prompt
