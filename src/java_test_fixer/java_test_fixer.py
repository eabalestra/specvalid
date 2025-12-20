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
    def _has_top_level_comma(expression: str) -> bool:
        depth = 0
        in_single_quote = False
        in_double_quote = False
        escape = False

        for ch in expression:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
                continue
            if ch == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
                continue
            if in_single_quote or in_double_quote:
                continue
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth = max(depth - 1, 0)
            elif ch == "," and depth == 0:
                return True
        return False

    @staticmethod
    def remove_assertions_from_test(test: str) -> str:

        def replacement_logic(match):
            """Determine appropriate replacement based on expression content."""
            try:
                expression = match.group(2)
            except IndexError:
                expression = ""

            if not expression:
                return "// assertion removed;"

            if expression and (re.search(r"->|::", expression) is not None):
                return f"// assertion removed: {expression};"

            if JavaTestFixer._has_top_level_comma(expression):
                return f"// assertion removed: {expression};"

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
            r"\b(?:[\w$]+\.)*(assertTrue|assertFalse)\s*\(\s*\"[^\"]*\"\s*,\s*(.*?)\s*\)\s*;",
            r"\b(?:[\w$]+\.)*(assertEquals|assertNotEquals)\s*\(\s*\"[^\"]*\"\s*,\s*[^,]+\s*,"
            r"\s*(.*?)\s*\)\s*;",
            r"\b(?:[\w$]+\.)*(assertSame|assertNotSame|assertArrayEquals|"
            r"assertIterableEquals|assertLinesMatch)\s*\(\s*\"[^\"]*\"\s*,\s*[^,]+\s*,"
            r"\s*(.*?)\s*\)\s*;",
            r"\b(?:[\w$]+\.)*(assertTimeout|assertTimeoutPreemptively)\s*\(\s*\"[^\"]*\"\s*,\s*[^,]+\s*,"
            r"\s*(.*?)\s*\)\s*;",
            # JUnit assertions with single argument (assertTrue, assertFalse)
            r"\b(?:[\w$]+\.)*(assertTrue|assertFalse)\s*\(\s*(.*?)\s*\)\s*;",
            r"\b(?:[\w$]+\.)*(assertNull|assertNotNull|assertInstanceOf)\s*\(\s*(.*?)\s*\)\s*;",
            # JUnit assertions with two arguments (assertEquals, assertNotEquals, etc.)
            r"\b(?:[\w$]+\.)*(assertEquals|assertNotEquals|assertSame|assertNotSame|"
            r"assertArrayEquals|assertIterableEquals|assertLinesMatch)\s*\(\s*[^,]+\s*,\s*(.*?)\s*\)\s*;",
            r"\b(?:[\w$]+\.)*(assertTimeout|assertTimeoutPreemptively)\s*\(\s*[^,]+\s*,\s*(.*?)\s*\)\s*;",
            # assertThat statements (Hamcrest/AssertJ style)
            r"\b(?:[\w$]+\.)*(assertThat)\s*\(\s*(.*?)\s*,\s*.*?\)\s*;",
            r"\b(?:[\w$]+\.)*(assertThrows|assertThrowsExactly)\s*\(\s*[^,]+\s*,\s*(.*?)\s*\)\s*;",
            r"\b(?:[\w$]+\.)*(assertDoesNotThrow)\s*\(\s*(.*?)\s*\)\s*;",
            r"\b(?:[\w$]+\.)*(assertAll)\s*\(\s*(.*?)\s*\)\s*;",
            r"\b(?:[\w$]+\.)*(assumeTrue|assumeFalse|assumeNotNull|assumeNoException|assumingThat)\s*\(\s*(.*?)\s*\)\s*;",
            r"\b(?:[\w$]+\.)*(assumeThat)\s*\(\s*(.*?)\s*,\s*.*?\)\s*;",
            # Java native assert statements
            r"\b(assert)\s+(.*?)(?:\s*:\s*.*?)?\s*;",
        ]

        result = test
        for pattern in patterns_to_remove:
            compiled_pattern = re.compile(pattern, re.DOTALL)
            result = compiled_pattern.sub(replacement_logic, result)

        # Handle fail statements separately (these should always be commented)
        fail_patterns = [
            (r"\b(?:[\w$]+\.)*(fail)\s*\(\s*\"[^\"]*\"\s*\)\s*;", r"// fail removed;"),
            (r"\b(?:[\w$]+\.)*(fail)\s*\(\s*\"[^\"]*\"\s*,\s*.*?\)\s*;", r"// fail removed;"),
            (r"\b(?:[\w$]+\.)*(fail)\s*\(\s*.*?\)\s*;", r"// fail removed;"),
        ]

        comment_only_patterns = [
            r"\b(?:[\w$]+\.)*(assertThat|assertThatThrownBy|assertThatCode|"
            r"assertThatExceptionOfType|assertThatIllegalArgumentException|"
            r"assertThatIllegalStateException|assertThatNullPointerException)\b.*?;",
        ]

        for pattern, replacement in fail_patterns:
            compiled_pattern = re.compile(pattern, re.DOTALL)
            result = compiled_pattern.sub(replacement, result)

        for pattern in comment_only_patterns:
            compiled_pattern = re.compile(pattern, re.DOTALL)
            result = compiled_pattern.sub("// assertion removed;", result)

        # Clean up any qualified prefixes left from prior replacements.
        assertion_prefixes = (
            r"(?:org\.junit\.Assert|org\.junit\.Assume|junit\.framework\.Assert|"
            r"org\.junit\.jupiter\.api\.Assertions|org\.junit\.jupiter\.api\.Assumptions|"
            r"org\.testng\.Assert|org\.testng\.AssertJUnit|"
            r"org\.assertj\.core\.api\.Assertions|org\.assertj\.core\.api\.BDDAssertions|"
            r"org\.hamcrest\.MatcherAssert|"
            r"Assert|Assertions|Assume|Assumptions|MatcherAssert|BDDAssertions)"
        )
        result = re.sub(
            rf"\b{assertion_prefixes}\.\s*(//\s*(?:assertion|fail)\s+removed[:;])",
            r"\1",
            result,
        )
        result = re.sub(
            rf"\b{assertion_prefixes}\.\s*(?!(?:assert|assume|fail)\w*)",
            "",
            result,
        )

        return result
