import shutil
import subprocess
from daikon.daikon import Daikon
from file_operations.file_ops import FileOperations
from java_test_appender.java_test_appender import JavaTestApender
from java_test_compiler.java_build_tool_compiler import JavaTestCompilationException
from java_test_compiler.java_test_compiler import JavaTestCompiler
from java_test_driver.java_test_driver import JavaTestDriver
from java_test_file_updater.java_test_file_updater import JavaTestFileUpdater
from java_test_suite.java_test_suite import JavaTestSuite
from llmservice.llm_service import LLMService
from logger.logger import Logger
from prompt.prompt_id import PromptID
from services.java_llmtesgen_service import JavaLLMTestGenService
from subject.subject import Subject
from testgen.java_test_generator import JavaTestGenerator

import os

SPECVALD_OUTPUT_DIR = "output"


def select_models(
    llm_service: LLMService, models_list: list[str], models_prefix: str | None
):
    # include only supported models
    models = []
    if models_prefix is not None:
        models = llm_service.get_model_ids_startswith(models_prefix)
        if len(models) == 0:
            raise ValueError("Invalid models prefix.")
    else:
        if (
            models_list is None
            or models_list == ""
            or models_list == []
            or models_list == [""]
        ):
            models = llm_service.get_all_models()
        else:
            all_models = llm_service.get_all_models()
            for m in all_models:
                if m in models_list:
                    models.append(m)
        if len(models) == 0:
            raise ValueError("No model selected.")
    return models


def select_prompts(prompts_list):
    # include only supported prompts
    prompt_IDs = []
    if (
        prompts_list is None
        or prompts_list == ""
        or prompts_list == []
        or prompts_list == [""]
    ):
        prompt_IDs = PromptID.all()
    else:
        for p in prompts_list:
            for p1 in PromptID.all():
                if p == p1.name or "PromptID." + p == p1.name:
                    prompt_IDs.append(p1)
    return prompt_IDs


def _create_subject_output_directory(subject_id):
    subject_output_dir = os.path.join(SPECVALD_OUTPUT_DIR, subject_id)
    os.makedirs(subject_output_dir, exist_ok=True)
    return subject_output_dir


def _init_subdirectory(subject_output_dir, subdir_name: str):
    subdir = os.path.join(subject_output_dir, subdir_name)
    if os.path.exists(subdir):
        shutil.rmtree(subdir)
    os.makedirs(subdir, exist_ok=True)
    return subdir


class Core:
    def __init__(self, args) -> None:
        self.args = args
        self.class_name = os.path.basename(args.target_class_src).replace(".java", "")
        self.subject_id = f"{self.class_name}_{args.method}"
        self.subject = Subject(
            args.target_class_src,
            args.buckets_assertions_file,
            args.method,
            JavaTestSuite(args.test_suite, args.target_class_src, self.subject_id),
            JavaTestDriver(args.test_driver),
        )
        self.compiler = JavaTestCompiler(args.target_class_src)
        self.output_dir = _create_subject_output_directory(self.subject_id)
        self.logs_output_dir = _init_subdirectory(self.output_dir, "logs")

    def run_testgen(self, args):
        try:
            # Parse arguments
            java_class_src = args.target_class_src
            method = args.method
            java_test_suite = args.test_suite
            java_test_driver = args.test_driver
            spec_file = args.buckets_assertions_file

            class_name = os.path.basename(java_class_src).replace(".java", "")
            subject_id = f"{class_name}_{method}"

            # Set up output directory for the subject
            subject_output_dir = _create_subject_output_directory(subject_id)
            subject_output_testgen_dir = _init_subdirectory(subject_output_dir, "test")

            # Setup logging
            logger = Logger(self.logs_output_dir + "/testgen.log")
            timestamp_logger = Logger(self.logs_output_dir + "/testgen_timestamp.log")

            # Log the arguments
            logger.log(f"Running test generation for {subject_id}.")
            logger.log(f"Arguments: {args}")

            # Setup the Java test suite and driver files
            generated_test_suite = JavaTestSuite(
                java_class_src, java_test_suite, subject_id
            )
            generated_test_driver = JavaTestDriver(args.test_driver)

            subject = Subject(
                java_class_src,
                spec_file,
                method,
                generated_test_suite,
                generated_test_driver,
            )
            java_test_generator = JavaTestGenerator(subject)

            # Service for test generation
            testgen_service = JavaLLMTestGenService(
                subject, java_test_generator, logger, timestamp_logger
            )

            # Select models and prompts
            models = select_models(
                java_test_generator.llm_service, args.models_list, args.models_prefix
            )
            prompt_IDs = select_prompts(args.prompts_list)

            # Run test generation using LLM's
            testgen_service.run(prompts=prompt_IDs, models=models)
            subject.test_suite.write_test_suite(
                os.path.join(subject_output_testgen_dir, f"{subject_id}LlmTest.java")
            )

            # TODO: uncomment this for testing
            # subject.test_suite.test_list = JavaTestSuite.extract_tests_from_file(
            #     "tests/suite_for_testing.java"
            # )

            logger.log(
                f"Processing {len(subject.test_suite.test_list)} tests for {subject_id}."
            )

            # Fix the generated test suite
            fixed_test_cases = subject.test_suite.repair_java_tests()
            fixed_tests_summary = "\n\n".join(fixed_test_cases)
            FileOperations.write_file(
                os.path.join(
                    subject_output_testgen_dir, f"{subject_id}LlmFixedTest.java"
                ),
                fixed_tests_summary,
            )

            # Discard tests that cannot be compiled
            compiler = JavaTestCompiler(java_class_src)
            compiled_test_cases = []
            for test in fixed_test_cases:
                try:
                    compiler.compile(test, with_tool=True)
                    compiled_test_cases.append(test)
                except JavaTestCompilationException as e:
                    logger.log_warning(f"Test discarded - Compilation error:\n{e}")

            compiled_tests_summary = "\n\n".join(compiled_test_cases)
            FileOperations.write_file(
                os.path.join(
                    subject_output_testgen_dir, f"{subject_id}LlmCompilableTest.java"
                ),
                compiled_tests_summary,
            )

            logger.log(f"Compiled {len(compiled_test_cases)} tests successfully.")

            # Set up the suite and driver for append the generated tests
            new_test_suite_path = JavaTestFileUpdater.prepare_test_file(
                java_test_suite, "Augmented", is_driver=False
            )
            new_test_driver_path = JavaTestFileUpdater.prepare_test_file(
                java_test_driver, "Augmented", is_driver=True
            )

            # Append the tests to the suite and driver
            appender = JavaTestApender()
            appender.insert_tests_into_suite(new_test_suite_path, compiled_test_cases)
            appender.insert_tests_into_driver(new_test_driver_path, compiled_test_cases)

            logger.log("> Test generation completed successfully.")
        except Exception as e:
            print(f"❌ Error: {e}")
            exit(1)

    def run_invariant_filter(self):
        try:
            subject = self.subject

            # Prepare the augmented test driver name for Daikon
            augmented_test_driver_name = (
                os.path.basename(self.args.test_driver).replace(".java", "")
                + "Augmented"
            )
            augmented_test_driver_fq_name = (
                subject.test_driver.get_package_name()
                + "."
                + augmented_test_driver_name
            )

            subject_output_dir = _create_subject_output_directory(self.subject_id)

            # Set up output directory for the subject
            subject_daikon_output_dir = _init_subdirectory(subject_output_dir, "daikon")
            subject_specs_output_dir = _init_subdirectory(subject_output_dir, "specs")

            # Setup logging
            logger = Logger(self.logs_output_dir + "/invfilter.log")

            logger.log(f"Running dynamic invariant filtering for {self.subject_id}.")
            logger.log(f"Arguments: {self.args}")

            self.compiler.compile_project()
            logger.log("Project compiled successfully.")

            daikon = Daikon(
                subject,
                augmented_test_driver_name,
                augmented_test_driver_fq_name,
                subject_daikon_output_dir,
            )

            logger.log(
                f"Run Dynamic Comparability Analysis from driver: "
                f"{augmented_test_driver_name}"
            )
            daikon.run_dyn_comp()

            logger.log(
                f"Run Chicory DTrace generation from driver: {augmented_test_driver_name}"
            )
            daikon.run_chicory_dtrace_generation()

            logger.log(
                f"Run Daikon Invariant Checker from driver: {augmented_test_driver_name}"
            )
            invalid_invs = daikon.run_invariant_checker(self.args.specfuzzer_invs_file)
            invalid_invs = f"{subject_daikon_output_dir}/invs.csv"

            # Build fully-qualified class name relative to src/main/java
            full_qualified_class_name = self.args.target_class_src.replace("\\", "/")
            if "/src/main/java/" in full_qualified_class_name:
                full_qualified_class_name = full_qualified_class_name.split(
                    "/src/main/java/"
                )[1]
            full_qualified_class_name = full_qualified_class_name.rstrip(".java")
            if full_qualified_class_name.endswith(".java"):
                full_qualified_class_name = full_qualified_class_name[:-5]

            full_qualified_class_name = full_qualified_class_name.replace("/", ".")

            cmd = [
                "python3",
                "scripts/filter_invariants_of_interest.py",
                invalid_invs,
                full_qualified_class_name,
                self.args.method,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            logger.log(result.stdout)

            cmd = [
                "python3",
                "scripts/extract_non_filtered_assertions.py",
                self.args.specfuzzer_assertions_file,
                f"{subject_specs_output_dir}/interest-specs.csv",
                self.class_name,
                self.args.method,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            logger.log(result.stdout)
        except Exception as e:
            print(f"❌ Error: {e}")
            exit(1)
