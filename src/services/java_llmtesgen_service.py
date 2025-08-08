import os
import time
from typing import List

from exceptions.java_test_compilation_exception import JavaTestCompilationException
from java_code_extractor.java_code_extractor import JavaCodeExtractor
from java_test_compiler.java_test_compiler import JavaTestCompiler
from prompt.prompt_id import PromptID
from subject.subject import Subject
from testgen.java_test_generator import JavaTestGenerator
from logger.logger import Logger

MAX_COMPILE_ATTEMPTS = int(os.getenv("MAX_COMPILE_ATTEMPTS", "3"))


class JavaLLMTestGenService:
    def __init__(
        self,
        subject: Subject,
        test_generator: JavaTestGenerator,
        logger: Logger,
        timestamp_logger: Logger,
    ):
        self.subject = subject
        self.test_generator = test_generator
        self.logger = logger
        self.timestamp_logger = timestamp_logger
        self.assertions_from_specfuzzer = self.subject.collect_specs()
        self.code_extractor = JavaCodeExtractor()
        self.compiler = JavaTestCompiler(str(self.subject.class_path_src))

    def run(self, prompts: list, models: list):
        self.logger.log(f"Starting test generation for {self.subject}...")
        total_time = 0.0
        for assertion in self.assertions_from_specfuzzer:
            assertion = self.subject.specs.transform_specification_vars(assertion)
            self.logger.log(f"Generating test for assertion: {assertion}")
            start_time = time.time()

            # Use LLMs to generate tests that invalidate the assertion
            llm_response = self.test_generator.generate_test(
                class_code=self.subject.class_code,
                method_code=self.subject.method_code,
                spec=assertion,
                prompt_ids=prompts,
                models_ids=models,
            )
            elapsed_time = time.time() - start_time
            total_time += elapsed_time

            generated_tests = self.reprompt_until_valid(llm_response, models)

            for test in generated_tests:
                self.subject.test_suite.add_test(test)

            self.logger.log(f"LLM response: {llm_response}")
            self.timestamp_logger.log(
                f"Test generation for assertion '{assertion}' took "
                f"{elapsed_time:.2f} seconds"
            )
        self.timestamp_logger.log(
            f"Total test generation time: {total_time:.2f} seconds"
        )
        self.logger.log(f"Finished test generation for {self.subject}.")

    def reprompt_until_valid(self, llm_response: str, models: List[str]) -> List[str]:
        test_list = []
        for attempt in range(1, MAX_COMPILE_ATTEMPTS + 1):
            test_list = self._extract_tests_from_response(llm_response)
            test_suite = "\n".join(test_list)
            try:
                self.compiler.compile(test=test_suite, with_tool=True)
                self.logger.log(f"Compilation successful on attempt {attempt}.")
                break
            except JavaTestCompilationException as e:
                self.logger.log_warning(
                    f"Compilation failed on attempt {attempt}: \n{e}"
                )
                llm_response = self.test_generator.generate_test(
                    class_code=self.subject.class_code,
                    method_code=self.subject.method_code,
                    spec=llm_response + "\n" + str(e),
                    prompt_ids=[PromptID.NOT_COMPILABLE],
                    models_ids=models,
                )
        return test_list

    def _extract_tests_from_response(self, llm_response: str) -> List[str]:
        parsed_tests = self.code_extractor.extract_tests_from_response(llm_response)
        cleaned_tests = []
        for test in parsed_tests:
            test = self.subject.test_suite.remove_assertions_from_test(test)
            cleaned_tests.append(test)
        return cleaned_tests
