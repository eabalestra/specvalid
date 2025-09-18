from pathlib import Path
import shutil
import subprocess
import tempfile

from exceptions.java_test_compilation_exception import JavaTestCompilationException
from java_test_compiler.template import TEST_TEMPLATE


class JavaBuildToolCompiler:
    def __init__(self, project_root: Path = Path(".")):
        self.project_root = project_root
        self.build_tool = self._detect_build_tool()

    def compile(self, test: str) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            self._prepare_workspace(tmp_dir)
            self._write_test_file(tmp_dir, test)
            return self._invoke_build(tmp_dir)

    def _compile_with_maven(self, work_dir: Path) -> None:
        raise NotImplementedError("Maven compilation not implemented yet")

    def _prepare_workspace(self, tmp_dir: Path) -> None:
        self._copy_build_files(tmp_dir)
        prod_src = self.project_root / "src" / "main" / "java"
        if prod_src.exists():
            dest_prod = tmp_dir / "src" / "main" / "java"
            shutil.copytree(prod_src, dest_prod)

    def _write_test_file(self, tmp_dir: Path, test: str) -> None:
        test_src_dir = tmp_dir / "src" / "test" / "java"
        test_src_dir.mkdir(parents=True, exist_ok=True)
        test_file_content = TEST_TEMPLATE.replace("{test_method}", test)
        test_file_path = test_src_dir / "GeneratedTest.java"
        test_file_path.write_text(test_file_content)

    def _invoke_build(self, tmp_dir: Path) -> None:
        if self.build_tool == "gradle":
            self._compile_with_gradle(tmp_dir)
        elif self.build_tool == "maven":
            self._compile_with_maven(tmp_dir)

    def _detect_build_tool(self) -> str:
        if (self.project_root / "build.gradle").exists() or (
            self.project_root / "build.gradle.kts"
        ).exists():
            return "gradle"
        if (self.project_root / "pom.xml").exists():
            return "maven"
        return "javac"

    def _compile_with_gradle(self, work_dir: Path) -> None:
        try:
            result = subprocess.run(
                ["./gradlew", "clean"],
                cwd=work_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            result = subprocess.run(
                ["./gradlew", "clean", "assemble", "testClasses", "-x", "test"],
                cwd=work_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                raise JavaTestCompilationException(f"{result.stderr}")
        except subprocess.CalledProcessError as e:
            raise JavaTestCompilationException(f"Gradle compilation failed: {e.stderr}")

    def _copy_build_files(self, target_dir: Path) -> None:
        pom = self.project_root / "pom.xml"
        if pom.exists():
            shutil.copy(pom, target_dir / "pom.xml")
        for fname in (
            "build.gradle",
            "build.gradle.kts",
            "settings.gradle",
            "settings.gradle.kts",
        ):
            src = self.project_root / fname
            if src.exists():
                shutil.copy(src, target_dir / fname)
        for fname in ("gradlew", "gradlew.bat"):
            src = self.project_root / fname
            if src.exists():
                shutil.copy(src, target_dir / fname)
        gradle_dir = self.project_root / "gradle"
        if gradle_dir.exists():
            shutil.copytree(gradle_dir, target_dir / "gradle")

        # Copy libs directory if it exists (for local JAR dependencies)
        libs_dir = self.project_root / "libs"
        if libs_dir.exists():
            shutil.copytree(libs_dir, target_dir / "libs")
