

from java_test_driver.java_test_driver import JavaTestDriver
from java_test_suite.java_test_suite import JavaTestSuite
from llmservice.llm_service import LLMService
from logger.logger import Logger
from prompt.prompt_id import PromptID
from services.java_tesgen_service import JavaTestGenService
from subject.subject import Subject
from testgen.java_test_generator import JavaTestGenerator

import os

SPECVALD_OUTPUT_DIR = "output"


def select_models(
        llm_service: LLMService,
        models_list: list[str],
        models_prefix: str | None
):
    # include only supported models
    models = []
    if models_prefix is not None:
        models = llm_service.get_model_ids_startswith(models_prefix)
        if len(models) == 0:
            raise ValueError("Invalid models prefix.")
    else:
        if models_list is None or models_list == "" or models_list == [] or models_list == [""]:
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
    if prompts_list is None or prompts_list == "" or prompts_list == [] or prompts_list == [""]:
        prompt_IDs = PromptID.all()
    else:
        for p in prompts_list:
            for p1 in PromptID.all():
                if p == p1.name or "PromptID."+p == p1.name:
                    prompt_IDs.append(p1)
    return prompt_IDs


def _get_subject_output_dir(java_class_src, method):
    class_name = os.path.basename(java_class_src).replace(".java", "")
    subject_output_dir = os.path.join(
        SPECVALD_OUTPUT_DIR, f"{class_name}_{method}")
    os.makedirs(subject_output_dir, exist_ok=True)
    return subject_output_dir


def run_testgen(args):
    try:
        java_class_src = args.target_class_src
        method = args.method
        java_test_suite = args.test_suite
        spec_file = args.assertions_file

        subject_output_dir = _get_subject_output_dir(java_class_src, method)

        logger = Logger(subject_output_dir + "/testgen.log")
        timestamp_logger = Logger(
            subject_output_dir + "/testgen_timestamp.log")

        logger.log(f"Arguments: {args}")

        generated_test_suite = JavaTestSuite(java_test_suite)
        generated_test_driver = JavaTestDriver()
        subject = Subject(
            java_class_src,
            spec_file,
            method,
            generated_test_suite,
            generated_test_driver
        )
        java_test_generator = JavaTestGenerator(subject)

        service = JavaTestGenService(
            subject,
            java_test_generator,
            logger,
            timestamp_logger
        )
        models = select_models(java_test_generator.llm_service,
                               args.models_list,
                               args.models_prefix)
        prompt_IDs = select_prompts(args.prompts_list)

        service.run(prompts=prompt_IDs, models=models)
    except ValueError as e:
        print(f"Error: {e}")
        return
    print("> Done")
