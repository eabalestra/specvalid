import os
from typing import Dict, List
from exceptions.java_test_compilation_exception import JavaTestCompilationException
from java_code_extractor.java_code_extractor import JavaCodeExtractor
from java_test_compiler.java_test_compiler import JavaTestCompiler
from llmservice.llm_service import LLMService

from logger.logger import Logger
from prompt.template_factory import PromptTemplateFactory

from prompt.prompt_template import PromptID
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
        self, class_code, method_code, spec, prompt_ids=PromptID.all(), models_ids=[]
    ):
        generated_test_cases_by_model = {}
        self.prompts = []

        for pid in prompt_ids:
            self._generate_prompts(pid, class_code, method_code, spec)

        for mid in models_ids:
            if mid not in generated_test_cases_by_model:
                generated_test_cases_by_model[mid] = []

            for pid in prompt_ids:
                llm_generated_cases = self._execute(pid, mid)
                generated_test_cases_by_model[mid].extend(llm_generated_cases)

        return generated_test_cases_by_model

    def _generate_prompts(self, prompt_id, class_code, method_code, spec):
        prompt = PromptTemplateFactory.create_prompt(
            prompt_id, class_code, method_code, spec
        )
        self.prompts.append(prompt)

    def _execute(self, pid, mid) -> List[str]:
        responses = []
        for prompt in self.prompts:
            if prompt.id is not pid:
                continue

            response = self.llm_service.execute_prompt(
                mid, prompt.generate_prompt(), prompt.format_instructions
            )

            if response is not None:
                self.logger.log(
                    f"LLM response for prompt {pid} and model {mid}: {response}"
                )

                tests_from_response = self._extract_tests_from_response(response)
                if tests_from_response:
                    for test in tests_from_response:
                        test = self._reprompt_until_validate(mid, test)
                        responses.append(test)

        return responses

    def _extract_tests_from_response(self, llm_response: str) -> List[str]:
        code_extractor = JavaCodeExtractor()
        parsed_tests = code_extractor.extract_tests_from_response(llm_response)
        cleaned_tests = []
        for test in parsed_tests:
            test = self.subject.test_suite.java_test_fixer.repair_java_test(test)
            cleaned_tests.append(test)
        return cleaned_tests

    def _reprompt_until_validate(self, model_id: str, test: str) -> str:
        for attempt in range(1, MAX_COMPILE_ATTEMPTS + 1):
            compilation = self._attempt_compilation([test])

            if compilation["success"]:
                return test

            # Check if errors list is not empty before accessing index 0
            if not compilation["errors"]:
                self.logger.log_warning(
                    f"No compilation errors found for attempt {attempt}"
                )
                continue

            prompt = self._build_enhanced_prompt(test, compilation["errors"][0])

            response = self.llm_service.execute_prompt(model_id, prompt, "")

            if response is not None:
                extracted_tests = self._extract_tests_from_response(response)
                # Check if extracted_tests is not empty before accessing index 0
                if extracted_tests:
                    test = extracted_tests[0]
                else:
                    self.logger.log_warning(
                        f"No tests extracted from LLM response in attempt {attempt}"
                    )
                    continue

        return test

    def _attempt_compilation(self, tests: List[str]) -> Dict:
        try:
            test_suite = "\n".join(tests)
            self.compiler.compile(test=test_suite, with_tool=True)
            return {"success": True, "errors": []}

        except JavaTestCompilationException as e:
            return {"success": False, "errors": [str(e)]}
        except Exception as e:
            return {"success": False, "errors": [f"Unexpected error: {str(e)}"]}

    def _build_enhanced_prompt(self, unit_test: str, error_msg: str) -> str:
        base_prompt = """
I need you to fix an error in a unit test, an error occurred while compiling

The unit test is:
```
{unit_test}
```

The error message is:
```
{error_message}
```

The unit test is testing the method `{method_sig}` in the class `{class_name}`,
the source code of the method under test and its class is:
```
{full_fm}
```

```
The signatures of other methods in its class are `{other_method_sigs}`
```

Please fix the error in the unit test and return the whole fixed unit test.
You can use Junit 5, Mockito 3 and reflection. No explanation is needed.
        """
        return base_prompt.format(
            unit_test=unit_test,
            error_message=error_msg,
            method_sig=self.subject.method_sig,
            class_name=self.subject.class_name,
            full_fm=self.subject.class_code,
            other_method_sigs=self.subject.other_method_sigs,
        )
