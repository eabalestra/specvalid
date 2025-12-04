import time
from collections import defaultdict

from generators.verification_only import VerificationOnlyGenerator
from logger.logger import Logger
from prompt.prompt_template import PromptID
from subject.subject import Subject
from verification.verdict_parser import VerificationVerdict


class VerificationOnlyService:
    def __init__(
        self,
        subject: Subject,
        generator: VerificationOnlyGenerator,
        logger: Logger,
    ):
        self.subject = subject
        self.generator = generator
        self.logger = logger
        self.assertions_from_specfuzzer = sorted(self.subject.collect_specs())

    def run(
        self, prompts: list[PromptID], models: list[str]
    ) -> dict[str, list[VerificationVerdict]]:
        if not self.assertions_from_specfuzzer:
            self.logger.log("No specifications found. Skipping verification.")
            return {}

        aggregated_results: dict[str, list[VerificationVerdict]] = defaultdict(list)
        total_time = 0.0

        for assertion in self.assertions_from_specfuzzer:
            transformed_spec = self.subject.specs.transform_specification_vars(
                assertion
            )
            self.logger.log(
                f"Verifying assertion: {transformed_spec}"
            )
            start_time = time.time()

            responses = self.generator.generate_verification(
                class_code=self.subject.class_code,
                method_code=self.subject.method_code,
                spec=transformed_spec,
                raw_spec=assertion,
                prompt_ids=prompts,
                models_ids=models,
            )

            elapsed = time.time() - start_time
            total_time += elapsed

            for model_id, verdicts in responses.items():
                aggregated_results[model_id].extend(verdicts)

            self.logger.log(
                f"Verification for assertion '{transformed_spec}' took {elapsed:.2f} seconds"
            )

        self.logger.log(
            f"Finished verification for {len(self.assertions_from_specfuzzer)} specs in {total_time:.2f} seconds."
        )

        return dict(aggregated_results)
