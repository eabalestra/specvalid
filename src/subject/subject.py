
import os
from zipfile import Path

from code_extractor.code_extractor import CodeExtractor
from java_test_driver.java_test_driver import JavaTestDriver
from java_test_suite.java_test_suite import JavaTestSuite
from specs.specs import Specs


class Subject:
    specs: Specs
    test_suite: JavaTestSuite
    test_driver: JavaTestDriver

    def __init__(
        self,
        class_path_src: str,
        spec_file: str,
        method_name: str,
        java_test_suite: str,
    ):
        self.class_code = self._load_class_code(class_path_src)
        self.method_code = self._load_method_code(class_path_src, method_name)
        self.specs = Specs(spec_file)

    def collect_specs(self) -> set:
        return self.specs.parse_and_collect_specs()

    def _load_class_code(self, class_path_src: str) -> str:
        if not os.path.exists(class_path_src):
            raise FileNotFoundError(
                f"Class source file not found: {class_path_src}")
        with open(class_path_src, 'r') as file:
            return file.read()

    def _load_method_code(self, class_path_src: str, method_name: str) -> str:
        code_extractor = CodeExtractor()
        class_code = self._load_class_code(class_path_src)
        return code_extractor.extract_method_code(class_code, method_name)
