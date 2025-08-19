import os
import json
from typing import Dict, List
from java_test_compiler.java_test_compiler import JavaTestCompiler
from exceptions.java_test_compilation_exception import JavaTestCompilationException
from file_operations.file_ops import FileOperations
from logger.logger import Logger


class ModelTestProcessor:
    """
    Handles processing of tests organized by model through different phases:
    raw -> fixed -> compiled
    """

    def __init__(self, logger: Logger, java_class_src: str):
        self.logger = logger
        self.compiler = JavaTestCompiler(java_class_src)

    def process_tests_by_model(self, test_suite, output_dir: str) -> Dict:
        """
        Process tests by model through fix and compile phases

        Returns:
            Dict with model statistics: {model_id: {phase: stats}}
        """
        model_stats = {}

        for model_id in test_suite.get_all_models():
            self.logger.log(f"Processing tests from model: {model_id}")

            raw_tests = test_suite.get_tests_by_model(model_id)
            model_stats[model_id] = {
                "raw": {"count": len(raw_tests), "tests": raw_tests}
            }

            # Phase 1: Fix tests
            fixed_tests = self._fix_tests(raw_tests, test_suite)
            model_stats[model_id]["fixed"] = {
                "count": len(fixed_tests),
                "tests": fixed_tests,
            }

            # Phase 2: Compile tests
            compiled_tests = self._compile_tests(fixed_tests, model_id)
            model_stats[model_id]["compiled"] = {
                "count": len(compiled_tests),
                "tests": compiled_tests,
            }

            # Write files for each phase
            self._write_model_phase_files(model_id, output_dir, model_stats[model_id])

        return model_stats

    def _fix_tests(self, raw_tests: List[str], test_suite) -> List[str]:
        """Fix/repair tests using the test suite's repair functionality"""
        fixed_tests = []
        for test in raw_tests:
            try:
                # Remove assertions and apply fixes
                fixed_test = test_suite.remove_assertions_from_test(test)
                fixed_test = test_suite.java_test_fixer.repair_java_test(fixed_test)
                fixed_tests.append(fixed_test)
            except Exception as e:
                self.logger.log_warning(f"Failed to fix test: {e}")
        return fixed_tests

    def _compile_tests(self, fixed_tests: List[str], model_id: str) -> List[str]:
        """Compile tests and return only those that compile successfully"""
        compiled_tests = []
        for i, test in enumerate(fixed_tests):
            try:
                self.compiler.compile(test, with_tool=True)
                compiled_tests.append(test)
            except JavaTestCompilationException as e:
                self.logger.log_warning(
                    f"Model {model_id} - Test {i+1} discarded - Compilation error: {e}"
                )
            except Exception as e:
                self.logger.log_warning(
                    f"Model {model_id} - Test {i+1} discarded - Unexpected error: {e}"
                )
        return compiled_tests

    def _write_model_phase_files(
        self, model_id: str, output_dir: str, model_data: Dict
    ):
        """Write files for all phases of a specific model"""
        model_dir = os.path.join(output_dir, "by_model", model_id.replace("/", "_"))
        os.makedirs(model_dir, exist_ok=True)

        for phase in ["raw", "fixed", "compiled"]:
            if phase in model_data:
                tests = model_data[phase]["tests"]
                count = model_data[phase]["count"]

                # Write test file
                if tests:
                    joined_tests = "\n\n".join(tests)
                    test_file = os.path.join(model_dir, f"{phase}_tests.java")
                    FileOperations.write_file(test_file, joined_tests)

                # Write metadata
                metadata = {
                    "model_id": model_id,
                    "phase": phase,
                    "test_count": count,
                    "success_rate": self._calculate_success_rate(model_data, phase),
                }
                metadata_file = os.path.join(model_dir, f"{phase}_metadata.json")
                with open(metadata_file, "w") as f:
                    json.dump(metadata, f, indent=2)

    def _calculate_success_rate(self, model_data: Dict, current_phase: str) -> float:
        """Calculate success rate for current phase vs previous phase"""
        if current_phase == "raw":
            return 100.0

        phase_order = ["raw", "fixed", "compiled"]
        current_idx = phase_order.index(current_phase)

        if current_idx == 0:
            return 100.0

        prev_phase = phase_order[current_idx - 1]
        prev_count = model_data[prev_phase]["count"]
        current_count = model_data[current_phase]["count"]

        if prev_count == 0:
            return 0.0

        return (current_count / prev_count) * 100.0

    def generate_model_comparison_report(self, model_stats: Dict, output_dir: str):
        """Generate a comparison report across all models"""
        analysis_dir = os.path.join(output_dir, "analysis")
        os.makedirs(analysis_dir, exist_ok=True)

        comparison = {"summary": {}, "by_model": {}, "ranking": {}}

        # Calculate statistics by model
        for model_id, stats in model_stats.items():
            comparison["by_model"][model_id] = {
                "raw_count": stats["raw"]["count"],
                "fixed_count": stats["fixed"]["count"],
                "compiled_count": stats["compiled"]["count"],
                "fix_success_rate": self._calculate_success_rate(stats, "fixed"),
                "compile_success_rate": self._calculate_success_rate(stats, "compiled"),
                "overall_success_rate": (
                    stats["compiled"]["count"] / stats["raw"]["count"] * 100.0
                    if stats["raw"]["count"] > 0
                    else 0.0
                ),
            }

        # Calculate overall summary
        total_raw = sum(stats["raw"]["count"] for stats in model_stats.values())
        total_compiled = sum(
            stats["compiled"]["count"] for stats in model_stats.values()
        )

        comparison["summary"] = {
            "total_models": len(model_stats),
            "total_raw_tests": total_raw,
            "total_compiled_tests": total_compiled,
            "overall_success_rate": (
                total_compiled / total_raw * 100.0 if total_raw > 0 else 0.0
            ),
        }

        # Create ranking by success rate
        model_rankings = sorted(
            comparison["by_model"].items(),
            key=lambda x: x[1]["overall_success_rate"],
            reverse=True,
        )
        comparison["ranking"]["by_success_rate"] = [
            {"model": model, "success_rate": data["overall_success_rate"]}
            for model, data in model_rankings
        ]

        # Write comparison report
        report_file = os.path.join(analysis_dir, "model_comparison.json")
        with open(report_file, "w") as f:
            json.dump(comparison, f, indent=2)

        self.logger.log(f"Model comparison report written to: {report_file}")
        return comparison
