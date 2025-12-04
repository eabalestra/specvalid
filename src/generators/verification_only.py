from llmservice.llm_service import LLMService
from logger.logger import Logger
from prompt.prompt_template import PromptID
from prompt.template_factory import PromptTemplateFactory
from subject.subject import Subject
from verification.verdict_parser import (
    InvalidVerificationResponseError,
    VerificationVerdict,
    parse_verification_response,
)


class VerificationOnlyGenerator:
    def __init__(self, subject: Subject, logger: Logger):
        self.prompts = []
        self.logger = logger
        self.subject = subject
        self.llm_service = LLMService()

    def generate_verification(
        self,
        class_code,
        method_code,
        spec,
        raw_spec: str = "",
        prompt_ids=None,
        models_ids=None,
    ) -> dict[str, list[VerificationVerdict]]:
        prompt_ids = prompt_ids or PromptID.all()
        models_ids = models_ids or []

        verification_cases_by_model: dict[str, list[VerificationVerdict]] = {}
        self.prompts = []

        for pid in prompt_ids:
            self._generate_prompts(pid, class_code, method_code, spec)

        for mid in models_ids:
            if mid not in verification_cases_by_model:
                verification_cases_by_model[mid] = []

            for pid in prompt_ids:
                llm_generated_cases = self._execute(pid, mid, spec, raw_spec)
                verification_cases_by_model[mid].extend(llm_generated_cases)

        return verification_cases_by_model

    def _generate_prompts(self, prompt_id, class_code, method_code, spec):
        prompt = PromptTemplateFactory.create_prompt(
            prompt_id, class_code, method_code, spec
        )
        self.prompts.append(prompt)

    def _execute(self, pid, mid, spec, raw_spec: str) -> list[VerificationVerdict]:
        verdicts: list[VerificationVerdict] = []
        for prompt in self.prompts:
            if prompt.id != pid:
                continue

            response = self.llm_service.execute_prompt(
                mid, prompt.generate_prompt(), prompt.format_instructions
            )

            if response is not None:
                self.logger.log(
                    f"LLM response for prompt {pid} and model {mid}: {response}"
                )
                try:
                    parsed = parse_verification_response(
                        response,
                        expected_spec=spec,
                        raw_spec=raw_spec,
                        model_id=mid,
                        prompt_id=pid,
                    )
                except InvalidVerificationResponseError as exc:
                    self.logger.log_error(
                        f"Unable to parse verification response for prompt {pid} "
                        f"and model {mid}: {exc}"
                    )
                    continue
                verdicts.extend(parsed)

        return verdicts
