import os
from typing import List

from java_code_extractor.java_code_extractor import JavaCodeExtractor
from java_test_compiler.java_test_compiler import JavaTestCompiler
from java_test_fixer.java_test_fixer import JavaTestFixer
from llmservice.llm_service import LLMService
from logger.logger import Logger
from prompt.prompt_template import PromptID
from prompt.template_factory import PromptTemplateFactory
from specs.specs import Specs
from subject.subject import Subject

MAX_COMPILE_ATTEMPTS = int(os.getenv("MAX_COMPILE_ATTEMPTS", "3"))


class JavaTestGenerator:
    def __init__(self, subject: Subject, logger: Logger):
        self.llm_service = LLMService()
        self.subject = subject
        self.prompts = []
        self.compiler = JavaTestCompiler(str(self.subject.class_path_src))
        self.logger = logger

    def generate_test(
        self,
        class_code,
        method_code,
        spec,
        raw_spec: str = "",
        prompt_ids=None,
        models_ids=None,
    ):
        prompt_ids = prompt_ids or PromptID.all()
        models_ids = models_ids or []

        generated_test_cases_by_model = {}
        self.prompts = []

        for pid in prompt_ids:
            self._generate_prompts(pid, class_code, method_code, spec)

        for mid in models_ids:
            if mid not in generated_test_cases_by_model:
                generated_test_cases_by_model[mid] = []

            for pid in prompt_ids:
                llm_generated_cases = self._execute(pid, mid, spec, raw_spec)
                generated_test_cases_by_model[mid].extend(llm_generated_cases)

        return generated_test_cases_by_model

    def _generate_prompts(self, prompt_id, class_code, method_code, spec):
        # if not any(p.id == prompt_id for p in self.prompts):
        prompt = PromptTemplateFactory.create_prompt(
            prompt_id, class_code, method_code, spec
        )
        self.prompts.append(prompt)

    def _execute(self, pid, mid, spec, raw_spec: str) -> List[str]:
        responses = []
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

                tests_from_response = self._prepare_tests_from_response(response)

                if tests_from_response:
                    for test in tests_from_response:
                        # Validate and fix the test
                        validated_test = self._reprompt_until_validate(mid, test)

                        # Version with spec annotation
                        test_with_spec = Specs.add_spec_annotation(validated_test, spec)
                        test_with_specs = Specs.add_spec_annotation(
                            test_with_spec, raw_spec
                        )
                        responses.append(test_with_specs)

                        # Version without assert wrappers
                        test_without_wrappers = (
                            JavaTestFixer.remove_assertions_from_test(test_with_specs)
                        )
                        responses.append(test_without_wrappers)
        return responses

    def _reprompt_until_validate(self, model_id: str, test: str) -> str:
        for attempt in range(1, MAX_COMPILE_ATTEMPTS + 1):
            compilation = self.compiler._attempt_test_compilation([test])

            if compilation["success"] is True:
                return test

            if not compilation["errors"]:
                self.logger.log_warning(
                    f"No compilation errors but success=False in attempt {attempt}."
                )
                return test

            prompt = PromptTemplateFactory.create_fix_prompt(
                test, compilation["errors"][0], self.subject
            )
            response = self.llm_service.execute_prompt(model_id, prompt, "")

            if response is not None:
                extracted_tests = self._prepare_tests_from_response(response)
                if extracted_tests:
                    test = extracted_tests[0]
                    test = self.subject.test_suite.java_test_fixer.repair_java_test(
                        test
                    )
                else:
                    self.logger.log_warning(
                        f"No tests extracted in attempt {attempt}. "
                        f"Keeping original for next try."
                    )
                    continue

        self.logger.log_warning(
            f"Max attempts reached for test. Returning last version "
            f"(may be invalid):\n{test}"
        )
        return test

    def _prepare_tests_from_response(self, llm_response: str) -> List[str]:
        code_extractor = JavaCodeExtractor()
        parsed_tests = code_extractor.extract_tests_from_response(llm_response)
        cleaned_tests = []
        for test in parsed_tests:
            test = self.subject.test_suite.java_test_fixer.repair_java_test(test)
            cleaned_tests.append(test)
        return cleaned_tests

    # def generate_test(
    #     self, class_code, method_code, spec, prompt_ids=PromptID.all(), models_ids=[]
    # ):
    #     if not prompt_ids or not models_ids:
    #         raise ValueError("prompt_ids and models_ids required.")
    #     self.prompts = []
    #     generated_test_cases_by_model = {mid: [] for mid in models_ids}

    #     for pid in set(prompt_ids):
    #         self._generate_prompts(pid, class_code, method_code, spec)

    #     with concurrent.futures.ThreadPoolExecutor() as executor:
    #         futures = {
    #             executor.submit(self._process_model, mid, prompt_ids, spec): mid
    #             for mid in models_ids
    #         }
    #         for future in concurrent.futures.as_completed(futures):
    #             mid = futures[future]
    #             generated_test_cases_by_model[mid].extend(future.result())

    #     return generated_test_cases_by_model

    # def _process_model(self, mid, prompt_ids, spec):
    #     responses = []
    #     for pid in prompt_ids:
    #         llm_generated_cases = self._execute(pid, mid, spec)
    #         responses.extend(llm_generated_cases)
    #     return responses
