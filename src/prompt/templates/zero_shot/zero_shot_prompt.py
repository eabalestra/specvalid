from prompt.prompt_template import Prompt
from prompt.templates.zero_shot.template import BASE_TEMPLATE


class ZeroShotPrompt(Prompt):

    def generate_prompt(self):
        return BASE_TEMPLATE.format(
            spec=self.spec, method_code=self.method_code, class_code=self.class_code
        )
