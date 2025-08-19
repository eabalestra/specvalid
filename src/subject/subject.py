import os
from pathlib import Path

from java_code_extractor.java_code_extractor import JavaCodeExtractor
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
        java_test_suite: JavaTestSuite,
        java_test_driver: JavaTestDriver,
    ):
        self.class_path_src = Path(class_path_src)
        self.class_code = self._load_class_code(class_path_src)
        self.method_code = self._load_method_code(class_path_src, method_name)
        self.specs = Specs(spec_file, class_path_src, method_name)
        self.test_suite = java_test_suite
        self.test_driver = java_test_driver
        self.root_dir = self._find_project_root()
        self.class_name = self.class_path_src.stem
        self.method_sig = JavaCodeExtractor.extract_method_signature(self.method_code)
        self.other_method_sigs = JavaCodeExtractor.extract_other_method_signatures(
            self.class_code
        )

    def collect_specs(self) -> set:
        return self.specs.parse_and_collect_specs()

    def _load_class_code(self, class_path_src: str) -> str:
        if not os.path.exists(class_path_src):
            raise FileNotFoundError(f"Class source file not found: {class_path_src}")
        with open(class_path_src, "r") as file:
            return file.read()

    def _load_method_code(self, class_path_src: str, method_name: str) -> str:
        code_extractor = JavaCodeExtractor()
        class_code = self._load_class_code(class_path_src)
        return code_extractor.extract_method_code(class_code, method_name)

    def _find_project_root(self) -> Path:
        current = self.class_path_src
        while True:
            if (current / "build.gradle").exists() or (
                current / "build.gradle.kts"
            ).exists():
                return current
            if (current / "pom.xml").exists():
                return current
            parent = current.parent
            if parent == current:
                break
            current = parent
        return self.class_path_src
