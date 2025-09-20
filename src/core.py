import shutil
import subprocess
from daikon.daikon import Daikon
from file_operations.file_ops import FileOperations
from java_test_appender.java_test_appender import JavaTestApender
from java_test_compiler.java_test_compiler import JavaTestCompiler
from java_test_driver.java_test_driver import JavaTestDriver
from java_test_file_updater.java_test_file_updater import JavaTestFileUpdater
from java_test_suite.java_test_suite import JavaTestSuite
from llmservice.llm_service import LLMService
from logger.logger import Logger

from prompt.prompt_template import PromptID
from services.java_llmtesgen_service import JavaLLMTestGenService
from subject.subject import Subject
from testgen.java_test_generator import JavaTestGenerator
from testgen.model_test_processor import ModelTestProcessor

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


def _init_subdirectory(
    subject_output_dir, subdir_name: str, preserve_existing: bool = False
):
    subdir = os.path.join(subject_output_dir, subdir_name)
    if os.path.exists(subdir) and not preserve_existing:
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
        self.logs_output_dir = _init_subdirectory(
            self.output_dir, "logs", preserve_existing=True
        )

    def run_testgen(self, args):
        try:
            # Parse arguments
            java_class_src = args.target_class_src
            method = args.method
            java_test_suite = args.test_suite
            spec_file = args.buckets_assertions_file

            class_name = os.path.basename(java_class_src).replace(".java", "")
            subject_id = f"{class_name}_{method}"

            # Set up output directory for the subject
            subject_output_dir = _create_subject_output_directory(subject_id)
            subject_output_testgen_dir = _init_subdirectory(
                subject_output_dir, "test", preserve_existing=args.reuse_tests
            )

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
            java_test_generator = JavaTestGenerator(subject, logger)

            # Service for test generation
            testgen_service = JavaLLMTestGenService(
                subject, java_test_generator, logger, timestamp_logger
            )

            # Select models and prompts
            models = select_models(
                java_test_generator.llm_service, args.models_list, args.models_prefix
            )
            prompt_IDs = select_prompts(args.prompts_list)

            # Check if we should reuse existing raw tests
            if args.reuse_tests:
                existing_tests_loaded = self._load_existing_raw_tests(
                    subject_output_testgen_dir, subject, logger
                )

                if not existing_tests_loaded:
                    # Run test generation using LLM's
                    logger.log("No existing raw tests found. Generating new tests...")
                    testgen_service.run(prompts=prompt_IDs, models=models)
                else:
                    logger.log("Reusing existing raw tests. Skipping LLM generation.")
            else:
                # Always run test generation using LLM's
                logger.log("Generating tests with LLMs...")
                testgen_service.run(prompts=prompt_IDs, models=models)

            subject.test_suite.write_test_suites_by_model(
                subject_output_testgen_dir, "raw"
            )

            for model_id in subject.test_suite.get_all_models():
                model_tests = subject.test_suite.get_tests_by_model(model_id)
                logger.log(f"Model {model_id} generated {len(model_tests)} tests")

            logger.log(
                f"Processing {len(subject.test_suite.test_list)} tests for {subject_id}."
            )

            model_processor = ModelTestProcessor(logger, java_class_src)
            model_stats = model_processor.process_tests_by_model(
                subject.test_suite, subject_output_testgen_dir
            )

            model_processor.generate_model_comparison_report(
                model_stats, subject_output_testgen_dir
            )

            for model_id, stats in model_stats.items():
                raw_count = stats["raw"]["count"]
                compiled_count = stats["compiled"]["count"]
                success_rate = compiled_count / raw_count * 100 if raw_count > 0 else 0
                logger.log(
                    f"Model {model_id}: {raw_count} raw -> {compiled_count} compiled "
                    f"({success_rate:.1f}% success)"
                )

            aggregated_compiled_tests = (
                subject.test_suite.get_all_compiled_tests_by_model(model_stats)
            )

            aggregated_compiled_summary = "\n\n".join(aggregated_compiled_tests)

            FileOperations.write_file(
                os.path.join(subject_output_testgen_dir, "all_compiled_tests.java"),
                aggregated_compiled_summary,
            )

            # Do not remove this line:
            #   it is used to read the logs and analyze the results
            logger.log(f"Compiled {len(aggregated_compiled_tests)} tests successfully.")
            logger.log("> Test generation completed successfully.")
        except Exception as e:
            print(f"❌ Error: {e}")
            exit(1)

    def run_invariant_filter(self):
        subject = self.subject
        logger = Logger(self.logs_output_dir + "/invfilter.log")
        logger.log(f"Running dynamic invariant filtering for {self.subject_id}.")
        logger.log(f"Arguments: {self.args}")

        models_dir = f"{self.output_dir}/test/by_model"

        available_models = []
        for model_name in os.listdir(models_dir):
            model_dir = os.path.join(models_dir, model_name)
            compiled_tests_file = os.path.join(model_dir, "compiled_tests.java")
            if os.path.exists(compiled_tests_file):
                available_models.append(model_name)

        if not available_models:
            logger.log_error("No models with compiled tests found - skipping Daikon")
            return

        logger.log(
            f"Found {len(available_models)} models with compiled tests: "
            f"{available_models}"
        )

        for model in available_models:
            print(f"> Running invariant filtering for tests from model: {model}")
            logger.log(f"Running invariant filtering for tests from model: {model}")
            self._process_model_invariant_filter(model, subject, logger)

    def _process_model_invariant_filter(self, model_id, subject, logger):
        try:
            model_output_dir = f"{self.output_dir}/test/by_model/{model_id}"

            final_tests = JavaTestSuite.extract_tests_from_file(
                f"{model_output_dir}/compiled_tests.java"
            )

            if not final_tests:
                logger.log(
                    "No tests found in all_compiled_tests.java - skipping Daikon"
                )
                return

            logger.log(f"Found {len(final_tests)} tests to validate against")

            renamed_tests = subject.test_suite._rename_test_methods(
                final_tests, "llmTest"
            )

            # Create model-specific directories
            model_daikon_dir = _init_subdirectory(model_output_dir, "daikon")
            model_specs_dir = _init_subdirectory(model_output_dir, "specs")

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

            # Clean first to remove any cached build artifacts
            self.compiler.compile_project(clean=True)
            logger.log("Project cleaned and compiled successfully.")

            # Set up the suite and driver for append the generated tests
            new_test_suite_path = JavaTestFileUpdater.prepare_test_file(
                self.args.test_suite, "Augmented", is_driver=False
            )
            new_test_driver_path = JavaTestFileUpdater.prepare_test_file(
                self.args.test_driver, "Augmented", is_driver=True
            )

            # Append the tests to the suite and driver
            appender = JavaTestApender()
            appender.insert_tests_into_suite(new_test_suite_path, renamed_tests)
            appender.insert_tests_into_driver(new_test_driver_path, renamed_tests)

            # Compile again with the Augmented files
            self.compiler.compile_project(clean=False)
            logger.log("Augmented files compiled successfully.")

            daikon = Daikon(
                subject,
                augmented_test_driver_name,
                augmented_test_driver_fq_name,
                model_daikon_dir,
            )

            logger.log(
                f"Run Dynamic Comparability Analysis from driver: "
                f"{augmented_test_driver_name}"
            )
            daikon.run_dyn_comp()

            logger.log(
                f"Run Chicory DTrace generation from driver: "
                f"{augmented_test_driver_name}"
            )
            daikon.run_chicory_dtrace_generation()

            logger.log(
                f"Run Daikon Invariant Checker from driver: {augmented_test_driver_name}"
            )

            invalid_invs = daikon.run_invariant_checker(self.args.specfuzzer_invs_file)

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
                model_specs_dir,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            logger.log(result.stdout)

            cmd = [
                "python3",
                "scripts/extract_non_filtered_assertions.py",
                self.args.specfuzzer_assertions_file,
                f"{model_specs_dir}/interest-specs.csv",
                self.class_name,
                self.args.method,
                model_specs_dir,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            logger.log(result.stdout)
        except Exception as e:
            logger.log_error(f"Error during invariant filtering: {e}")
            print(f"❌ Error during invariant filtering: {e}")
            return

    def _load_existing_raw_tests(self, output_dir: str, subject, logger) -> bool:
        """
        Load existing raw tests from by_model directory if they exist.
        Returns True if tests were loaded, False otherwise.
        """
        by_model_dir = os.path.join(output_dir, "by_model")

        if not os.path.exists(by_model_dir):
            return False

        models_loaded = 0
        total_tests_loaded = 0

        for model_name in os.listdir(by_model_dir):
            model_dir = os.path.join(by_model_dir, model_name)
            raw_tests_file = os.path.join(model_dir, "raw_tests.java")

            if os.path.exists(raw_tests_file):
                try:
                    # Extract tests from the raw_tests.java file
                    from java_test_suite.java_test_suite import JavaTestSuite

                    raw_tests = JavaTestSuite.extract_tests_from_file(raw_tests_file)

                    if raw_tests:
                        # Add tests to the test suite by model
                        for test in raw_tests:
                            subject.test_suite.add_test_by_model(model_name, test)

                        models_loaded += 1
                        total_tests_loaded += len(raw_tests)
                        logger.log(
                            f"Loaded {len(raw_tests)} raw tests from model: {model_name}"
                        )

                except Exception as e:
                    logger.log_warning(
                        f"Failed to load raw tests from {model_name}: {e}"
                    )

        if models_loaded > 0:
            logger.log(
                f"Successfully loaded {total_tests_loaded} raw tests "
                f"from {models_loaded} models"
            )
            return True
        else:
            return False
