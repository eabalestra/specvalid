import logging
from pathlib import Path
import shutil
import subprocess
import tempfile


class JavaBuildToolCompiler:
    def __init__(self, project_root: Path = Path(".")):
        self.project_root = project_root
        self.build_tool = self._detect_build_tool()

    def compile(self, test: str) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            print(f"Compiling test {test} in temporary directory {tmp_dir}")
            self._copy_build_files(tmp_dir)

            prod_src = self.project_root / "src" / "main" / "java"
            if prod_src.exists():
                dest_prod = tmp_dir / "src" / "main" / "java"
                shutil.copytree(prod_src, dest_prod)
                print("Copied production sources to isolated project")
                subprocess.run(["tree", "."], cwd=tmp_dir, check=True)

            if self.build_tool == "gradle":
                self._compile_with_gradle(tmp_dir, test)
            elif self.build_tool == "maven":
                self._compile_with_maven(tmp_dir, test)

    def _detect_build_tool(self) -> str:
        if (self.project_root / "build.gradle").exists() or (
            self.project_root / "build.gradle.kts"
        ).exists():
            return "gradle"
        if (self.project_root / "pom.xml").exists():
            return "maven"
        return "javac"

    def _compile_with_gradle(self, work_dir: Path, test: str) -> None:
        exe = str(work_dir / "gradlew") if (work_dir / "gradlew").exists() else "gradle"
        cmd = [exe, "test", "--tests", test, "--quiet"]
        subprocess.run(cmd, cwd=work_dir, check=True)

    def _compile_with_maven(self, work_dir: Path, test: str) -> None:
        raise NotImplementedError("Maven compilation not implemented yet")

    def _copy_build_files(self, target_dir: Path) -> None:
        pom = self.project_root / "pom.xml"
        if pom.exists():
            shutil.copy(pom, target_dir / "pom.xml")
            print("Copied pom.xml")
        for fname in (
            "build.gradle",
            "build.gradle.kts",
            "settings.gradle",
            "settings.gradle.kts",
        ):
            src = self.project_root / fname
            if src.exists():
                shutil.copy(src, target_dir / fname)
                print(f"Copied {fname}")
        for fname in ("gradlew", "gradlew.bat"):
            src = self.project_root / fname
            if src.exists():
                shutil.copy(src, target_dir / fname)
                print(f"Copied {fname}")
        gradle_dir = self.project_root / "gradle"
        if gradle_dir.exists():
            shutil.copytree(gradle_dir, target_dir / "gradle")
            print("Copied gradle wrapper directory")
