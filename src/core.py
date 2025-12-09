import glob
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from daikon.daikon import Daikon
from file_operations.file_ops import FileOperations
from generators.verification_only import VerificationOnlyGenerator
from java_test_appender.java_test_appender import JavaTestApender
from java_test_compiler.java_test_compiler import JavaTestCompiler
from java_test_driver.java_test_driver import JavaTestDriver
from java_test_file_updater.java_test_file_updater import JavaTestFileUpdater
from java_test_suite.java_test_suite import JavaTestSuite
from llmservice.llm_service import LLMService
from logger.logger import Logger
from prompt.prompt_template import PromptID
from services.java_llmtesgen_service import JavaLLMTestGenService
from services.verification_only_service import VerificationOnlyService
from specfuzzer.gen_mutated_traces import (
    MutatedTraceGenerationError,
    MutatedTraceGenerator,
)
from subject.subject import Subject
from testgen.java_test_generator import JavaTestGenerator
from testgen.model_test_processor import ModelTestProcessor


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


def _create_subject_output_directory(output_base_dir, subject_id):
    subject_output_dir = os.path.join(output_base_dir, subject_id)
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


def _expand_classpath(cp_str: str) -> str:
    """Expand classpath with globs to absolute paths."""
    parts = cp_str.split(os.pathsep)
    expanded = []
    for part in parts:
        if not part:
            continue
        if "*" in part:
            # Expand glob patterns and convert to absolute paths
            matched = glob.glob(part)
            expanded.extend([str(Path(p).resolve()) for p in matched])
        elif Path(part).exists():
            # Convert to absolute path
            expanded.append(str(Path(part).resolve()))
        else:
            # Keep as-is if path doesn't exist (might be needed)
            expanded.append(part)
    return os.pathsep.join(expanded)


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
        self.output_dir = _create_subject_output_directory(
            args.output_dir, self.subject_id
        )
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
            subject_output_dir = _create_subject_output_directory(
                args.output_dir, subject_id
            )
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

        if not os.path.isdir(models_dir):
            msg = (
                "❌ No per-model tests were found. "
                "Run test generation before invariant filtering."
            )
            logger.log_error(msg)
            print(msg)
            return

        available_models = []
        for model_name in os.listdir(models_dir):
            model_dir = os.path.join(models_dir, model_name)
            compiled_tests_file = os.path.join(model_dir, "compiled_tests.java")
            if os.path.exists(compiled_tests_file):
                available_models.append(model_name)

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
                try:
                    with open(self.args.specfuzzer_assertions_file, "r") as file:
                        set1 = {line.strip() for line in file}
                except FileNotFoundError:
                    msg = (
                        f"❌ Assertions file not found: "
                        f"{self.args.specfuzzer_assertions_file}"
                    )
                    logger.log_error(msg)
                    print(msg)
                    return
                except PermissionError:
                    msg = (
                        f"❌ Permission denied when accessing assertions file: "
                        f"{self.args.specfuzzer_assertions_file}"
                    )
                    logger.log_error(msg)
                    print(msg)
                    return
                set1 = {
                    item
                    for item in set1
                    if item
                    and not item.startswith(
                        "==========================================================================="
                    )
                    and ":::OBJECT" not in item
                    and ":::ENTER" not in item
                    and ":::EXIT" not in item
                }
                assertions_file_name = os.path.basename(
                    self.args.specfuzzer_assertions_file
                )
                logger.log(f"Specs from {assertions_file_name}: {len(set1)}")
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

            # Set up the suite and driver for append the generated tests
            new_test_suite_path = JavaTestFileUpdater.prepare_test_file(
                self.args.test_suite, "Augmented", is_driver=False
            )
            new_test_driver_path = JavaTestFileUpdater.prepare_test_file(
                self.args.test_driver, "Augmented", is_driver=True
            )

            # Clean first to remove any cached build artifacts
            self.compiler.compile_project(clean=True)
            logger.log("Project cleaned and compiled successfully.")

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
            try:
                daikon.run_dyn_comp()
            except RuntimeError as e:
                logger.log_error(f"Error during DynComp: {e}")

            logger.log(
                f"Run Chicory DTrace generation from driver: "
                f"{augmented_test_driver_name}"
            )
            try:
                daikon.run_chicory_dtrace_generation()
            except RuntimeError as e:
                logger.log_error(f"Error during Chicory DTrace generation: {e}")

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
            logger.log_error(f"❌ Error during invariant filtering: {e}")
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

    def run_verification_only(self):
        logger = Logger(self.logs_output_dir + "/verify_only.log")
        logger.log(f"Running verification only for {self.subject_id}.")
        logger.log(f"Arguments: {self.args}")

        try:
            subject = self.subject
            verification_output_dir = _init_subdirectory(
                self.output_dir, "verification"
            )
            by_model_dir = _init_subdirectory(verification_output_dir, "by_model")

            generator = VerificationOnlyGenerator(subject, logger)
            verification_service = VerificationOnlyService(subject, generator, logger)

            models = select_models(
                generator.llm_service, self.args.models_list, self.args.models_prefix
            )
            prompt_ids = select_prompts(self.args.prompts_list)

            logger.log(
                f"Running verification for {len(models)} models and "
                f"{len(prompt_ids)} prompts"
            )

            results_by_model = verification_service.run(prompt_ids, models)

            if not results_by_model:
                logger.log("No verification results were produced.")
                return

            summary = {}
            total_valid = 0
            total_invalid = 0

            for model_id, verdicts in results_by_model.items():
                model_dir = _init_subdirectory(by_model_dir, model_id)
                verdicts_payload = []
                for verdict in verdicts:
                    verdicts_payload.append(
                        {
                            "spec": verdict.spec,
                            "raw_spec": verdict.raw_spec,
                            "raw_response": verdict.raw_response,
                            "verdict": verdict.verdict,
                        }
                    )

                FileOperations.write_file(
                    os.path.join(model_dir, "verdicts.json"),
                    json.dumps(verdicts_payload, indent=2),
                )

                valid_count = sum(
                    1 for verdict in verdicts if verdict.verdict == "VALID"
                )
                invalid_count = sum(
                    1 for verdict in verdicts if verdict.verdict == "INVALID"
                )
                summary[model_id] = {
                    "total_responses": len(verdicts),
                    "valid": valid_count,
                    "invalid": invalid_count,
                }
                total_valid += valid_count
                total_invalid += invalid_count

            summary["totals"] = {
                "models": len(results_by_model),
                "responses": total_valid + total_invalid,
                "valid": total_valid,
                "invalid": total_invalid,
            }

            FileOperations.write_file(
                os.path.join(verification_output_dir, "summary.json"),
                json.dumps(summary, indent=2),
            )

            logger.log(f"Verification results saved in {verification_output_dir}")
        except Exception as exc:
            logger.log_error(f"❌ Error during verification: {exc}")
            print(f"❌ Error during verification: {exc}")
            exit(1)

    def run_bucketing_augmented(self):
        logger = Logger(self.logs_output_dir + "/bucketing.log")
        logger.log(f"Running bucketing (augmented) for {self.subject_id}.")
        logger.log(f"Arguments: {self.args}")
        try:
            models_dir = os.path.join(self.output_dir, "test", "by_model")
            if not os.path.isdir(models_dir):
                raise FileNotFoundError(
                    "No per-model tests were found. Run test generation first."
                )

            compiled_models = self._get_models_with_compiled_tests(models_dir)
            if not compiled_models:
                raise RuntimeError(
                    "No compiled tests found for any model. Cannot run bucketing."
                )

            logger.log(
                f"Found {len(compiled_models)} models with compiled tests: {list(compiled_models.keys())}"
            )

            for model_id, compiled_tests_path in compiled_models.items():
                logger.log(f"Running bucketing for model: {model_id}")
                self._run_bucketing_for_model(model_id, compiled_tests_path, logger)

        except MutatedTraceGenerationError as e:
            logger.log_error(f"❌ Error during bucketing: {e}")
            print(f"❌ Error during bucketing: {e}")
            exit(1)
        except Exception as e:
            logger.log_error(f"❌ Error during bucketing: {e}")
            print(f"❌ Error during bucketing: {e}")
            exit(1)

    def _run_bucketing_for_model(
        self, model_id: str, compiled_tests_path: str, logger: Logger
    ) -> None:
        compiled_tests = JavaTestSuite.extract_tests_from_file(compiled_tests_path)
        if not compiled_tests:
            logger.log_warning(
                f"Model {model_id} has no compiled tests. Skipping bucketing."
            )
            return

        logger.log(f"Loaded {len(compiled_tests)} compiled tests for model {model_id}")

        sanitized_suffix = self._sanitize_identifier(model_id)
        suite_suffix = f"Augmented{sanitized_suffix}"

        renamed_tests = self.subject.test_suite._rename_test_methods(  # pylint: disable=protected-access
            compiled_tests, f"llm{sanitized_suffix}"
        )

        test_suite_augmented = JavaTestFileUpdater.prepare_test_file(
            self.args.test_suite, suite_suffix, is_driver=False
        )
        driver_augmented = JavaTestFileUpdater.prepare_test_file(
            self.args.test_driver, suite_suffix, is_driver=True
        )

        logger.log("Cleaning project before updating suites")
        self.compiler.compile_project(clean=True)

        appender = JavaTestApender()
        appender.insert_tests_into_suite(test_suite_augmented, renamed_tests)
        appender.insert_tests_into_driver(driver_augmented, renamed_tests)

        logger.log("Compiling augmented project")
        self.compiler.compile_project(clean=False)

        bucketing_root = Path(
            _init_subdirectory(self.output_dir, "bucketing", preserve_existing=True)
        ).resolve()
        model_bucket_dir = Path(
            _init_subdirectory(bucketing_root, f"model_{sanitized_suffix}")
        ).resolve()
        daikon_dir = Path(_init_subdirectory(model_bucket_dir, "daikon")).resolve()
        setup_files_dir = Path(
            _init_subdirectory(model_bucket_dir, "setup-files")
        ).resolve()

        driver_augmented_name = os.path.basename(driver_augmented).replace(".java", "")
        driver_package = self.subject.test_driver.get_package_name()
        driver_augmented_fq = (
            f"{driver_package}.{driver_augmented_name}"
            if driver_package
            else driver_augmented_name
        )

        logger.log(
            f"Running DynComp and Chicory for driver {driver_augmented_fq} (model {model_id})"
        )

        daikon_runner = Daikon(
            self.subject,
            driver_augmented_name,
            driver_augmented_fq,
            daikon_dir,
        )

        daikon_runner.run_dyn_comp()
        daikon_runner.run_chicory_dtrace_generation()

        comparability_file = os.path.join(
            daikon_dir, f"{driver_augmented_name}.decls-DynComp"
        )

        major_home = os.environ.get("MAJOR_HOME")

        if not major_home:
            raise RuntimeError(
                "MAJOR_HOME environment variable is not set. Unable to run Major."
            )

        logger.log(
            f"Generating mutant traces with Major + Chicory for model {model_id}"
        )

        trace_generator = MutatedTraceGenerator(
            major_home=major_home,
            subject_root=str(self.subject.root_dir),
            target_class_src=self.args.target_class_src,
            driver_fq_name=driver_augmented_fq,
            driver_name=driver_augmented_name,
            comparability_file=comparability_file,
            classpath=daikon_runner.cp_for_daikon,
            setup_output_dir=setup_files_dir,
            logger=logger,
            timeout_seconds=600,
            chicory_timeout=600,
        )

        traces = trace_generator.generate()

        logger.log(
            f"Mutant traces ready at {trace_generator.traces_output_dir} ({len(traces)} entries)"
        )

        # Now run the filtering step - check each mutant against the SpecFuzzer invariants
        invs_file = str(Path(self.args.specfuzzer_invs_file).resolve())
        assertions_file = str(Path(self.args.specfuzzer_assertions_file).resolve())
        if not invs_file or not assertions_file:
            logger.log_warning(
                "SpecFuzzer invs/assertions not provided; skipping invariant filtering"
            )
            return

        repo_root = Path(__file__).resolve().parents[1]
        model_workdir = model_bucket_dir.resolve()
        mutant_invs_dir = Path(_init_subdirectory(model_bucket_dir, "mutant-invs"))

        # Seed invs-by-mutants.csv (required by single-mutant-result.py)
        base_mutants_csv = Path(repo_root / "base-invs-by-mutants.csv")
        target_mutants_csv = model_workdir / "invs-by-mutants.csv"
        if base_mutants_csv.exists():
            shutil.copyfile(base_mutants_csv, target_mutants_csv)
        elif not target_mutants_csv.exists():
            FileOperations.write_file(
                str(target_mutants_csv), "invariant,ppt,iteration,mutant\n"
            )

        # Mutants log to filter only relevant mutations (constructor/static/method)
        mutants_log = (
            trace_generator.traces_output_dir / f"{driver_augmented_name}-mutants.log"
        )
        mutants_log_lines: list[str] = []
        if mutants_log.exists():
            mutants_log_lines = mutants_log.read_text().splitlines()

        # Filtering step with optional time budget (90 minutes like in run-specfuzzer.sh)
        filtering_budget = 5400  # 90 minutes in seconds
        filtering_start_time = time.time()

        processed_mutants = 0
        for trace in sorted(trace_generator.traces_output_dir.glob("*.dtrace.gz")):
            # Chicory writes `<driver>-mN.dtrace.gz` and `<driver>-mN-objects.xml`
            base_no_ext = trace.name.replace(".dtrace.gz", "")
            objects_file = (trace.parent / f"{base_no_ext}-objects.xml").resolve()
            if not objects_file.exists():
                logger.log_warning(
                    f"Skipping mutant trace {trace} (objects file missing)"
                )
                continue

            # Filter by target scope using mutants.log
            # Only process mutants that affect: static methods, constructors, or the target method
            mutant_index = 0
            if base_no_ext.startswith(f"{driver_augmented_name}-m"):
                try:
                    mutant_index = int(base_no_ext.split("-m")[1])
                except ValueError:
                    mutant_index = 0

            if mutant_index and mutants_log_lines:
                if mutant_index - 1 < len(mutants_log_lines):
                    curr_mutant = mutants_log_lines[mutant_index - 1]
                    # Check if mutant is in target scope
                    # Process if: static method (class:) OR constructor (class@<init>) OR target method
                    is_in_scope = (
                        f"{self.class_name}:" in curr_mutant
                        or f"{self.class_name}@<init>" in curr_mutant
                        or (
                            self.class_name in curr_mutant
                            and self.args.method in curr_mutant
                        )
                    )

                    if not is_in_scope:
                        logger.log(
                            f"Skipping mutant {mutant_index} ({curr_mutant}): not in target scope"
                        )
                        continue
                    else:
                        logger.log(f"Processing mutant {mutant_index}: {curr_mutant}")

            invs_csv = model_workdir / "invs.csv"
            if invs_csv.exists():
                invs_csv.unlink()
            logger.log(f"InvariantChecker on mutant trace {trace}")
            trace_arg = os.path.relpath(trace, model_workdir)
            objects_arg = os.path.relpath(objects_file, model_workdir)

            # Expand classpath to absolute paths to avoid issues with relative paths
            expanded_cp = _expand_classpath(daikon_runner.cp_for_daikon)

            cmd = [
                "java",
                "-Xmx8g",
                "-cp",
                expanded_cp,
                "daikon.tools.InvariantChecker",
                "--conf",
                "--serialiazed-objects",
                objects_arg,
                invs_file,
                trace_arg,
            ]
            try:
                subprocess.run(
                    cmd,
                    check=True,
                    timeout=daikon_runner.invariant_timeout,
                    cwd=str(model_workdir),
                )
            except subprocess.CalledProcessError as exc:
                logger.log_warning(f"InvariantChecker failed for {trace.name}: {exc}")
            except subprocess.TimeoutExpired:
                logger.log_warning(
                    f"InvariantChecker timed out for {trace.name} after {daikon_runner.invariant_timeout}s"
                )

            if invs_csv.exists():
                dest_csv = mutant_invs_dir / f"{trace.stem}.csv"
                FileOperations.move_file(str(invs_csv), str(dest_csv))
                helper = repo_root / "scripts" / "single-mutant-result.py"
                if helper.exists():
                    cmd_helper = [
                        "python3",
                        str(helper),
                        str(dest_csv),
                        "1",
                        str(trace),
                    ]
                    try:
                        subprocess.run(cmd_helper, check=False, cwd=str(model_workdir))
                    except Exception as exc:  # noqa: BLE001
                        logger.log_warning(
                            f"single-mutant-result.py failed for {trace.name}: {exc}"
                        )
                processed_mutants += 1

            # Check time budget
            elapsed = time.time() - filtering_start_time
            if elapsed > filtering_budget:
                logger.log(
                    f"Filtering step finished due to timeout: {elapsed:.1f}s (budget: {filtering_budget}s)"
                )
                break

        filtering_sec = time.time() - filtering_start_time
        logger.log(
            f"Processed {processed_mutants} mutants for model {model_id} in {filtering_sec:.1f}s"
        )

        # Prepare output file names with specvalid prefix
        specvalid_prefix = (
            f"{self.class_name}-{self.args.method}-{sanitized_suffix}-specvalid"
        )

        # Copy invs-by-mutants.csv to output location
        mutka_file = model_workdir / "invs-by-mutants.csv"
        specvalid_mutka = model_bucket_dir / f"{specvalid_prefix}-invs-by-mutants.csv"
        if mutka_file.exists():
            shutil.copyfile(mutka_file, specvalid_mutka)
            logger.log(f"Mutation killing ability results saved in: {specvalid_mutka}")
        else:
            logger.log_warning(f"invs-by-mutants.csv not found at {mutka_file}")

        # Generate assertions file using Daikon PrintInvariants
        # This prints OBJECT and EXIT program points in Java format
        specvalid_assertions = model_bucket_dir / f"{specvalid_prefix}.assertions"
        logger.log(f"Writing assertions to file: {specvalid_assertions}")

        try:
            # Expand classpath to absolute paths
            expanded_cp = _expand_classpath(daikon_runner.cp_for_daikon)

            # Print OBJECT invariants
            cmd_object = [
                "java",
                "-cp",
                expanded_cp,
                "daikon.PrintInvariants",
                invs_file,
                "--ppt-select",
                f".{self.class_name}:::OBJECT",
                "--format",
                "java",
            ]
            result_object = subprocess.run(
                cmd_object,
                check=True,
                capture_output=True,
                text=True,
                timeout=daikon_runner.invariant_timeout,
            )

            # Print EXIT (postcondition) invariants
            cmd_exit = [
                "java",
                "-cp",
                expanded_cp,
                "daikon.PrintInvariants",
                invs_file,
                "--ppt-select",
                f".{self.class_name}.{self.args.method}.",
                "--format",
                "java",
            ]
            result_exit = subprocess.run(
                cmd_exit,
                check=True,
                capture_output=True,
                text=True,
                timeout=daikon_runner.invariant_timeout,
            )

            # Combine both outputs
            combined_output = result_object.stdout + result_exit.stdout
            FileOperations.write_file(str(specvalid_assertions), combined_output)
            logger.log(
                f"✓ Assertions file generated with {len(combined_output.splitlines())} lines"
            )

        except subprocess.CalledProcessError as exc:
            logger.log_warning(
                f"PrintInvariants failed, falling back to specfuzzer assertions: {exc}"
            )
            # Fallback: use the existing specfuzzer assertions file
            FileOperations.write_file(
                str(specvalid_assertions), FileOperations.read_file(assertions_file)
            )
        except subprocess.TimeoutExpired:
            logger.log_warning(
                "PrintInvariants timed out, falling back to specfuzzer assertions"
            )
            FileOperations.write_file(
                str(specvalid_assertions), FileOperations.read_file(assertions_file)
            )

        # Copy the inv.gz file to output location for reference
        specvalid_inv_gz = model_bucket_dir / f"{specvalid_prefix}.inv.gz"
        if Path(invs_file).exists():
            shutil.copyfile(invs_file, specvalid_inv_gz)
            logger.log(f"✓ Copied inv.gz to {specvalid_inv_gz}")

        # Run buckets-filter.py to generate bucketed assertions
        buckets_filter = repo_root / "scripts" / "buckets-filter.py"

        # The buckets-filter.py script expects .assertion (without 's') and generates -buckets.assertion
        # We need to create a temporary .assertion file (without 's') from the generated assertions
        temp_assertions_file = model_bucket_dir / f"{specvalid_prefix}.assertion"
        FileOperations.write_file(
            str(temp_assertions_file),
            FileOperations.read_file(str(specvalid_assertions)),
        )

        # The expected output file path (buckets-filter.py replaces .assertion with -buckets.assertion)
        temp_bucket_assertions = (
            model_bucket_dir / f"{specvalid_prefix}-buckets.assertion"
        )
        bucket_assertions_path = (
            model_bucket_dir / f"{specvalid_prefix}-buckets.assertions"
        )

        if buckets_filter.exists() and specvalid_mutka.exists():
            cmd_buckets = [
                "python3",
                str(buckets_filter),
                str(specvalid_mutka),
                str(temp_assertions_file),
                self.class_name,
                self.args.method,
            ]
            logger.log(f"Running buckets-filter.py: {' '.join(cmd_buckets)}")
            try:
                result = subprocess.run(
                    cmd_buckets,
                    check=True,
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                )
                logger.log(f"buckets-filter.py output:\n{result.stdout}")

                # Rename the output to use .assertions (with 's')
                if temp_bucket_assertions.exists():
                    shutil.move(
                        str(temp_bucket_assertions), str(bucket_assertions_path)
                    )
                    logger.log(
                        f"✓ Bucket assertions written to {bucket_assertions_path}"
                    )
                    logger.log(f"  Processed {processed_mutants} mutants")
                    # Read and log bucket statistics
                    with open(bucket_assertions_path, "r") as f:
                        first_lines = [f.readline().strip() for _ in range(2)]
                        logger.log(f"  Bucket stats: {first_lines}")
                else:
                    logger.log_warning(
                        f"buckets-filter.py completed but did not create {temp_bucket_assertions}"
                    )

                # Clean up temporary file
                if temp_assertions_file.exists():
                    temp_assertions_file.unlink()

            except subprocess.CalledProcessError as exc:
                logger.log_warning(
                    f"buckets-filter.py failed: {exc}\nStderr: {exc.stderr}"
                )
                # Fallback: copy assertions as buckets file
                FileOperations.write_file(
                    str(bucket_assertions_path),
                    FileOperations.read_file(str(specvalid_assertions)),
                )
                # Clean up temporary file
                if temp_assertions_file.exists():
                    temp_assertions_file.unlink()
                logger.log(
                    f"Bucket assertions written to {bucket_assertions_path} (no clustering applied - fallback)"
                )
        else:
            # Fallback: copy assertions as buckets file
            FileOperations.write_file(
                str(bucket_assertions_path),
                FileOperations.read_file(temp_assertions_file),
            )
            logger.log(
                f"Bucket assertions written to {bucket_assertions_path} (buckets-filter.py not found - fallback)"
            )

    def _get_models_with_compiled_tests(self, models_dir: str) -> dict:
        models = {}
        for model_name in sorted(os.listdir(models_dir)):
            model_path = os.path.join(models_dir, model_name)
            compiled_tests_file = os.path.join(model_path, "compiled_tests.java")
            if os.path.isfile(compiled_tests_file):
                models[model_name] = compiled_tests_file
        return models

    @staticmethod
    def _sanitize_identifier(name: str) -> str:
        sanitized = "".join(ch for ch in name if ch.isalnum())
        return sanitized if sanitized else "Model"
