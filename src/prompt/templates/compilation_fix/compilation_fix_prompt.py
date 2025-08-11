from prompt.prompt_template import Prompt


class CompilationFixPrompt(Prompt):
    def generate_prompt(self) -> str:
        NOT_COMPILABLE_PROMPT_TEMPLATE = """
In the provided response, the test code is not compilable.
Please fix the test code.
The provided response is:
{llm_response}
The class code for the test is:
{class_code}
The method under test is:
{method_code}
Answer with the fixed test code. In JUnit format, with @Test annotation.

"""
        return NOT_COMPILABLE_PROMPT_TEMPLATE.format(
            llm_response=self.spec,
            class_code=self.class_code,
            method_code=self.method_code,
        )
