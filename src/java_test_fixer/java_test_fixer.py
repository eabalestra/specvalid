import glob
import os
import re

from utils.utils import Utils


class JavaTestFixer:
    def __init__(self, path_to_class: str, path_to_suite: str):
        self.path_to_class = path_to_class
        self.path_to_suite = path_to_suite
        self.class_package = Utils.get_java_package_from_path(path_to_class)
        self.class_directory = os.path.dirname(path_to_class)
        self.class_package_files = glob.glob(
            os.path.join(self.class_directory, "*.java")
        )

    def repair_java_test(self, test_code: str) -> str:
        if test_code.strip() == "":
            return test_code
        test = self._add_throws_signature(test_code)
        test = self._replace_class_references(test)
        return self._add_test_annotation(test)

    def _add_test_annotation(self, test_code: str) -> str:
        # Add @Test annotation if not present
        if "@Test" not in test_code:
            test_code = f"@Test\n{test_code}"
        return test_code

    def _add_throws_signature(self, test_code: str) -> str:
        pattern = r"((public\s+)?void \w+\s*\([^)]*\))\s*(?:throws\s+[^\\{]*)?\s*\{"
        replacement = r"\1 throws Throwable {"
        return re.sub(pattern, replacement, test_code)

    def _replace_class_references(self, test_code: str) -> str:
        for file_path in self.class_package_files:
            file_name = os.path.splitext(os.path.basename(file_path))[0]
            prefix = f"{self.class_package}." if self.class_package else ""
            full_name = f"{prefix}{file_name}"
            # TODO: Modified pattern: allow class name followed by dot (for method calls)
            # but not preceded by word characters or dots
            # Also allow constructor calls where the class name is followed by "("
            pattern = re.compile(rf"(?<![\w\.]){re.escape(file_name)}(?=\.|\s|\(|$)")
            test_code = pattern.sub(full_name, test_code)
        return test_code

    @staticmethod
    def _contains_method_calls(expression: str) -> bool:
        """Check if an expression contains method calls that should be executed."""

        # Pattern to detect method calls
        method_call_pattern = (
            r"[a-zA-Z_$][a-zA-Z0-9_$]*(?:\.[a-zA-Z_$][a-zA-Z0-9_$]*)*\s*\("
        )

        # Check if expression contains method calls
        has_method_calls = bool(re.search(method_call_pattern, expression))

        if not has_method_calls:
            return False

        # Additional check: if it contains comparison operators,
        # it's likely a boolean expression that should be commented
        comparison_operators = ["==", "!=", "<=", ">=", "<", ">", "&&", "||"]
        has_comparisons = any(op in expression for op in comparison_operators)

        # If it has both method calls and comparisons, treat as boolean expression
        if has_comparisons:
            return False

        # If it's just method calls without comparisons, treat as executable
        return True

    @staticmethod
    def remove_assertions_from_test(test: str) -> str:

        def replacement_logic(match):
            """Determine appropriate replacement based on expression content."""
            try:
                expression = match.group(2)
            except IndexError:
                expression = ""

            # If expression contains method calls that should be executed,
            # keep it as executable statement
            if JavaTestFixer._contains_method_calls(expression):
                return f"{expression};"
            else:
                # If it's just a boolean comparison, comment it out
                return f"// assertion removed: {expression};"

        # Remove assertion wrappers for different types of assertions
        patterns_to_remove = [
            # JUnit assertions with message parameter (first argument is message)
            r"\b(assertTrue|assertFalse)\s*\(\s*\"[^\"]*\"\s*,\s*(.*?)\s*\)\s*;",
            r"\b(assertEquals|assertNotEquals)\s*\(\s*\"[^\"]*\"\s*,\s*[^,]+\s*,"
            r"\s*(.*?)\s*\)\s*;",
            # JUnit assertions with single argument (assertTrue, assertFalse)
            r"\b(assertTrue|assertFalse)\s*\(\s*(.*?)\s*\)\s*;",
            # JUnit assertions with two arguments (assertEquals, assertNotEquals, etc.)
            r"\b(assertEquals|assertNotEquals|assertSame|assertNotSame|"
            r"assertArrayEquals)\s*\(\s*[^,]+\s*,\s*(.*?)\s*\)\s*;",
            # assertThat statements (Hamcrest/AssertJ style)
            r"\b(assertThat)\s*\(\s*(.*?)\s*,\s*.*?\)\s*;",
            r"\b(assertNull|assertNotNull)\s*\(\s*(.*?)\s*\)\s*;",
            r"\b(assertThrows)\s*\(\s*[^,]+\s*,\s*(.*?)\s*\)\s*;",
            r"\b(assertDoesNotThrow)\s*\(\s*(.*?)\s*\)\s*;",
            r"\b(assertAll)\s*\(\s*(.*?)\s*\)\s*;",
            r"\b(assumeTrue|assumeFalse)\s*\(\s*(.*?)\s*\)\s*;",
            r"\b(assumeThat)\s*\(\s*(.*?)\s*,\s*.*?\)\s*;",
        ]

        result = test
        for pattern in patterns_to_remove:
            compiled_pattern = re.compile(pattern, re.DOTALL)
            result = compiled_pattern.sub(replacement_logic, result)

        # Handle fail statements separately (these should always be commented)
        fail_patterns = [
            (r"\b(fail)\s*\(\s*\"[^\"]*\"\s*\)\s*;", r"// fail removed;"),
            (r"\b(fail)\s*\(\s*\)\s*;", r"// fail removed;"),
        ]

        for pattern, replacement in fail_patterns:
            compiled_pattern = re.compile(pattern, re.DOTALL)
            result = compiled_pattern.sub(replacement, result)

        return result
