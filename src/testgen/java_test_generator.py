from llmservice.llm_service import LLMService

from prompt.template_factory import PromptTemplateFactory

from prompt.prompt_template import PromptID
from subject.subject import Subject


class JavaTestGenerator:
    def __init__(self, subject: Subject):
        self.llm_service = LLMService()
        self.subject = subject
        self.prompts = []
        self.llm_response = ""

    def generate_test(
        self, class_code, method_code, spec, prompt_ids=PromptID.all(), models_ids=[]
    ):
        self.llm_response = ""
        self.prompts = []

        for pid in prompt_ids:
            self._generate_prompts(pid, class_code, method_code, spec)

        for mid in models_ids:
            for pid in prompt_ids:
                llm_output = self._execute(pid, mid)
                self.llm_response += llm_output
        return self.llm_response

    def _generate_prompts(self, prompt_id, class_code, method_code, spec):
        prompt = PromptTemplateFactory.create_prompt(prompt_id, class_code, method_code, spec)
        self.prompts.append(prompt)

    def _execute(self, pid, mid):
        combined_responses = ""
        for prompt in self.prompts:
            if prompt.id is not pid:
                continue
            response = self.llm_service.execute_prompt(
                mid, prompt.generate_prompt(), prompt.format_instructions
            )
            if response is not None:
                combined_responses += response
        return combined_responses
