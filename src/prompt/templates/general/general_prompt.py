from prompt.prompt_template import Prompt
from prompt.templates.general.template import BASE_TEMPLATE


TEST_SECTION_TEMPLATE = """
[[CODE]]
{class_code}
[[METHOD]]
{method_code}
[[POSTCONDITION]]
{spec}
[[VERDICT]]

"""


class GeneralPrompt(Prompt):
    def generate_prompt(self) -> str:
        self.template = BASE_TEMPLATE
        prompt_template_section = TEST_SECTION_TEMPLATE
        prompt_template_section = prompt_template_section.format(
            class_code=self.class_code, method_code=self.method_code, spec=self.spec
        )
        self.prompt = self.template + prompt_template_section
        return self.prompt
