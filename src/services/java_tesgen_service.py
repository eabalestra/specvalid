import time

from java_code_extractor.java_code_extractor import JavaCodeExtractor
from subject.subject import Subject
from testgen.java_test_generator import JavaTestGenerator
from logger.logger import Logger


class JavaTestGenService:

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

            self.logger.log(f"LLM response: {llm_response}")

            test_code = self.process_llm_test_response(llm_response)
            self.subject.test_suite.add_test(test_code)

            self.logger.log(f"Generated test: \n{test_code}")
            self.timestamp_logger.log(
                f"Test generation for assertion '{assertion}' took "
                f"{elapsed_time:.2f} seconds"
            )
        self.timestamp_logger.log(
            f"Total test generation time: {total_time:.2f} seconds"
        )
        self.logger.log(f"Finished test generation for {self.subject}.")

    def process_llm_test_response(self, llm_response: str) -> str:
        test_code = self.code_extractor.extract_test_code_from_response(llm_response)
        test_code = self.subject.test_suite.remove_assertions_from_test(test_code)
        return test_code
