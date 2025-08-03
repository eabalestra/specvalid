import re
from typing import List

from file_operations.file_ops import FileOperations
from java_test_fixer.java_test_fixer import JavaTestFixer


class JavaTestSuite:

    def __init__(self, path_to_class: str, path_to_suite: str):
        self.path_to_class = path_to_class
        self.path_to_suite = path_to_suite
        self.java_test_fixer = JavaTestFixer(path_to_class, path_to_suite)
        self.tests = []

    def add_test(self, test_code: str):
        self.tests.append(test_code)

    def remove_assertions_from_test(self, test_code: str) -> str:
        assertion_regex = re.compile(
            r"^\s*(?:[a-zA-Z0-9_.]+\.)?(?:assert\w*\b.*?;|fail\w*\b.*?;).*$",
            re.MULTILINE | re.IGNORECASE,
        )
        return re.sub(assertion_regex, "", test_code)

    def repair_java_tests(self) -> list[str]:
        fixed_tests = []
        for test in self.tests:
            fixed_test = self.java_test_fixer.repair_java_test(test)
            fixed_tests.append(fixed_test)
        return self._rename_test_methods(fixed_tests, "llmTest")

    def write_test_suite(self):
        joined_test_cases = "\n\n".join(self.tests)
        FileOperations.write_file("suite.java", joined_test_cases)

    def _rename_test_methods(self, test_methods: List[str], new_name: str) -> List[str]:
        name_pattern = r"public void \w+\(\)"
        return [
            re.sub(name_pattern, f"public void {new_name}{i}()", test_method)
            for i, test_method in enumerate(test_methods)
        ]

    @staticmethod
    def extract_tests_from_file(source_test_file: str) -> List[str]:
        try:
            with open(source_test_file, "r", encoding="utf-8") as sf:
                content = sf.read()
            return JavaTestSuite.parse_test_from_string(content)
        except FileNotFoundError:
            print(f"File not found: {source_test_file}")
            return []
        except Exception as e:
            print(f"Error reading file {source_test_file}: {e}")
            return []

    @staticmethod
    def parse_test_from_string(content: str) -> List[str]:
        brace_count = 0
        test_methods = []
        extracted_test = []
        test_case_started = False
        lines = content.split("\n")
        test_start_pattern = re.compile(r"^\s*@Test")

        for line in lines:
            if test_start_pattern.match(line):
                test_case_started = True
            if test_case_started:
                extracted_test.append(line)
                brace_count += line.count("{") - line.count("}")
                if brace_count == 0 and line.strip().endswith("}"):
                    test_case_started = False
                    test_methods.append("\n".join(extracted_test))
                    extracted_test = []
        return test_methods
