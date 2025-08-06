from prompt.prompt_id import PromptID
from prompt.prompts import TEST_GENERATION_PROMPT


class Prompt:
    id: PromptID
    template: str
    prompt: str
    format_instructions: str

    class_code: str
    method_code: str
    spec: str

    def __init__(self, id=PromptID.General_V1, class_code="", method_code="", spec=""):
        self.id = id
        self.class_code = class_code
        self.method_code = method_code
        self.spec = spec
        self.format_instructions = ""
        self.instantiate_prompt_template()

    def instantiate_prompt_template(self):
        if self.id == PromptID.General_V1:
            self.template = TEST_GENERATION_PROMPT
            prompt_template_section = TEST_GENERATION_TEMPLATE
            prompt_template_section = prompt_template_section.format(
                class_code=self.class_code, method_code=self.method_code, spec=self.spec
            )
            self.prompt = self.template + prompt_template_section
        elif self.id == PromptID.General_V2:
            pass
        elif self.id == PromptID.NOT_COMPILABLE:
            template = NOT_COMPILABLE_PROMPT_TEMPLATE
            self.template = template.format(
                llm_response=self.spec,
                class_code=self.class_code,
                method_code=self.method_code,
            )
            self.prompt = self.template


TEST_GENERATION_TEMPLATE = """
[[CODE]]
{class_code}
[[METHOD]]
{method_code}
[[POSTCONDITION]]
{spec}
[[VERDICT]]

"""

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
