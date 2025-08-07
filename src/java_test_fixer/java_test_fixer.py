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
        test = self._add_throws_signature_(test_code)
        test = self._replace_class_references(test)
        return self._add_test_annotation(test)

    def _add_test_annotation(self, test_code: str) -> str:
        # Add @Test annotation if not present
        if "@Test" not in test_code:
            test_code = f"@Test\n{test_code}"
        return test_code

    def _add_throws_signature_(self, test_code: str) -> str:
        pattern = r"(public void \w+\(\))\s*(?:throws\s+[^\\{]*)?\s*\{"
        replacement = r"\1 throws Throwable {"
        return re.sub(pattern, replacement, test_code)

    def _replace_class_references(self, test_code: str) -> str:
        for file_path in self.class_package_files:
            file_name = os.path.splitext(os.path.basename(file_path))[0]
            prefix = f"{self.class_package}." if self.class_package else ""
            full_name = f"{prefix}{file_name}"
            pattern = re.compile(rf"(?<![\w\.]){re.escape(file_name)}(?![\w\.])")
            test_code = pattern.sub(full_name, test_code)
        return test_code
