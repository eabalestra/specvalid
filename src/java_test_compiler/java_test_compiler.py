from pathlib import Path

from java_test_compiler.java_build_tool_compiler import JavaBuildToolCompiler
from java_test_compiler.javac_compiler import JavacCompiler


class JavaTestCompiler:
    def __init__(self, class_path: str = "."):
        self.class_path = Path(class_path).resolve()
        self.project_root = self._find_project_root()

    def compile(self, test: str, with_tool: bool = True) -> None:
        if with_tool:
            return self._compile_test_with_build_tool(test)
        return self._compile_test_with_javac(test)

    def _find_project_root(self) -> Path:
        current = self.class_path
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
        return self.class_path

    def _compile_test_with_build_tool(self, test: str) -> None:
        build_compiler = JavaBuildToolCompiler(self.project_root)
        build_compiler.compile(test)

    def _compile_test_with_javac(self, test: str) -> None:
        javac_compiler = JavacCompiler()
        javac_compiler.compile(test)
