from __future__ import annotations

import glob
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional


class MutatedTraceGenerationError(RuntimeError):
    """Raised when we fail to generate traces for the mutants."""


@dataclass
class MutantTraceInfo:
    """Metadata for a generated mutant trace."""

    index: int
    dtrace_file: Path
    objects_file: Path


class MutatedTraceGenerator:
    """Generate Chicory traces for all Major mutants of a class."""

    def __init__(
        self,
        *,
        major_home: str,
        subject_root: str,
        target_class_src: str,
        driver_fq_name: str,
        driver_name: str,
        comparability_file: str,
        classpath: str,
        setup_output_dir: str,
        logger=None,
        timeout_seconds: int = 10,
        chicory_timeout: int | None = None,
    ) -> None:
        self.major_home = Path(major_home).expanduser().resolve()
        if not self.major_home.exists():
            raise MutatedTraceGenerationError(
                f"MAJOR_HOME does not exist: {self.major_home}"
            )

        self.major_javac = self.major_home / "bin" / "javac"
        if not self.major_javac.exists():
            raise MutatedTraceGenerationError(
                f"Major compiler not found at {self.major_javac}"
            )

        self.subject_root = Path(subject_root).resolve()
        self.target_class_src = Path(target_class_src).resolve()
        self.driver_fq_name = driver_fq_name
        self.driver_name = driver_name
        self.comparability_file = Path(comparability_file).resolve()
        self.classpath = self._expand_classpath(classpath)
        self.setup_output_dir = Path(setup_output_dir).resolve()
        self.logger = logger
        self.timeout_seconds = timeout_seconds
        self.chicory_timeout = chicory_timeout or timeout_seconds

        self.build_dir = self.subject_root / "build" / "classes" / "java" / "main"
        self.test_classes_dir = (
            self.subject_root / "build" / "classes" / "java" / "test"
        )
        self.subject_libs = self.subject_root / "libs" / "*"
        self.repo_root = Path(__file__).resolve().parents[2]

        self.major_classpath = self._expand_classpath(
            os.pathsep.join(
                [
                    str(self.build_dir),
                    str(self.subject_root / "libs" / "*.jar"),
                    str(self.repo_root / "libs" / "*.jar"),
                ]
            )
        )

        self.workspace_dir = self.setup_output_dir / "major_workspace"
        self.traces_output_dir = self.setup_output_dir / "mutants"

        self.src_main_dir = self.subject_root / "src" / "main" / "java"
        try:
            self.target_rel_path = self.target_class_src.relative_to(self.src_main_dir)
        except ValueError as exc:  # pragma: no cover - validated at runtime
            raise MutatedTraceGenerationError(
                "Target class must be located under src/main/java"
            ) from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate(self) -> List[MutantTraceInfo]:
        """Generate mutants and run Chicory on each of them.

        Returns:
            List[MutantTraceInfo]: metadata for every successfully processed
            mutant.  This includes the index used by Major and the produced
            Chicory artifacts.
        """

        self._prepare_directories()
        self._run_major()
        mutant_dirs = self._iter_mutant_dirs()

        trace_infos: List[MutantTraceInfo] = []
        for mutant_dir in mutant_dirs:
            index = int(mutant_dir.name)
            mutant_source = mutant_dir / self.target_rel_path
            if not mutant_source.exists():
                self._log(f"Skipping mutant {index}: missing source {mutant_source}")
                continue

            if not self._compile_mutant(mutant_source):
                continue
            dtrace_path = (
                self.traces_output_dir / f"{self.driver_name}-m{index}.dtrace.gz"
            )
            objects_path = (
                self.traces_output_dir / f"{self.driver_name}-m{index}-objects.xml"
            )
            if self._run_chicory(index, dtrace_path, objects_path):
                trace_infos.append(
                    MutantTraceInfo(
                        index=index, dtrace_file=dtrace_path, objects_file=objects_path
                    )
                )

        self._move_mutants_log()
        self._log(
            f"Generated Chicory traces for {len(trace_infos)} mutants. Output: {self.traces_output_dir}"
        )
        return trace_infos

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _log(self, message: str) -> None:
        if self.logger:
            self.logger.log(message)
        else:  # pragma: no cover - fallback for manual runs
            print(message)

    def _prepare_directories(self) -> None:
        if self.workspace_dir.exists():
            shutil.rmtree(self.workspace_dir)
        if self.traces_output_dir.exists():
            shutil.rmtree(self.traces_output_dir)

        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.traces_output_dir.mkdir(parents=True, exist_ok=True)

    def _run_major(self) -> None:
        cmd = [
            str(self.major_javac),
            "-cp",
            self.major_classpath,
            "-nowarn",
            "-J-Dmajor.export.mutants=true",
            "-XMutator:ALL",
            "-d",
            str(self.build_dir),
            str(self.target_class_src),
        ]
        self._run_command(
            cmd, cwd=self.workspace_dir, description="Generating mutants with Major"
        )

    def _iter_mutant_dirs(self) -> Iterable[Path]:
        mutants_root = self.workspace_dir / "mutants"
        if not mutants_root.exists():
            raise MutatedTraceGenerationError(
                f"Major did not produce mutants directory at {mutants_root}"
            )
        mutant_dirs = sorted(p for p in mutants_root.iterdir() if p.is_dir())
        if not mutant_dirs:
            raise MutatedTraceGenerationError("Major did not create any mutants")
        return mutant_dirs

    def _compile_mutant(self, mutant_source: Path) -> bool:
        cmd = [
            "javac",
            "-cp",
            self.major_classpath,
            "-g",
            str(mutant_source),
            "-d",
            str(self.build_dir),
        ]
        try:
            self._run_command(
                cmd,
                cwd=self.workspace_dir,
                description=f"Compiling mutant source {mutant_source}",
            )
            return True
        except MutatedTraceGenerationError as exc:
            self._log(f"Skipping mutant {mutant_source}: compilation failed ({exc})")
            return False

    def _run_chicory(self, index: int, dtrace_path: Path, objects_path: Path) -> bool:
        ppt_pattern = f"{self.driver_name}.*"
        dtrace_arg = os.path.relpath(dtrace_path, self.workspace_dir)
        objects_arg = os.path.relpath(objects_path, self.workspace_dir)
        cmd = [
            "java",
            "-cp",
            self.classpath,
            "daikon.Chicory",
            "--output-dir",
            str(self.traces_output_dir),
            "--comparability-file",
            str(self.comparability_file),
            "--ppt-omit-pattern",
            ppt_pattern,
            "--ppt-omit-pattern",
            "org.junit.*",
            "--dtrace-file",
            dtrace_arg,
            self.driver_fq_name,
            objects_arg,
        ]
        try:
            self._run_command(
                cmd,
                cwd=self.workspace_dir,
                description=f"Running Chicory for mutant {index}",
                timeout=self.chicory_timeout,
            )
        except MutatedTraceGenerationError as exc:
            # Chicory may still produce dtrace/objects even when exiting non-zero
            self._log(f"Chicory error for mutant {index}: {exc}")
        # Accept the mutant if artifacts exist
        if dtrace_path.exists() and objects_path.exists():
            return True
        self._log(
            f"Skipping mutant {index}: missing artifacts (dtrace: {dtrace_path.exists()}, objects: {objects_path.exists()})"
        )
        return False

    def _move_mutants_log(self) -> None:
        log_path = self.workspace_dir / "mutants.log"
        if log_path.exists():
            dest_name = f"{self.driver_name}-mutants.log"
            shutil.move(str(log_path), str(self.traces_output_dir / dest_name))

    def _run_command(
        self,
        cmd: List[str],
        *,
        cwd: Optional[Path] = None,
        description: str,
        timeout: Optional[int] = None,
    ) -> None:
        self._log(f"{description} -> {' '.join(cmd)}")
        process = subprocess.Popen(
            cmd,
            cwd=str(cwd) if cwd else None,
            preexec_fn=os.setsid,  # Create a new process group
        )
        try:
            process.wait(timeout=timeout or self.timeout_seconds)
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, cmd)
        except subprocess.TimeoutExpired as exc:  # pragma: no cover - runtime guard
            # Kill the entire process group
            os.killpg(os.getpgid(process.pid), 9)
            process.wait()  # Wait for the process to be killed
            raise MutatedTraceGenerationError(
                f"Command timed out after {timeout or self.timeout_seconds}s ({description})"
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise MutatedTraceGenerationError(
                f"Command failed ({description}): {exc}"
            ) from exc

    def _build_classpath(self, entries: List[Path]) -> str:
        cp_parts: List[str] = []
        for entry in entries:
            pattern = str(entry)
            if "*" in pattern:
                cp_parts.extend(glob.glob(pattern))
            elif Path(pattern).exists():
                cp_parts.append(pattern)
        cp_parts.extend(glob.glob(str(self.repo_root / "libs" / "*.jar")))
        return os.pathsep.join(cp_parts)

    def _expand_classpath(self, cp_str: str) -> str:
        parts = cp_str.split(os.pathsep)
        expanded: List[str] = []
        for part in parts:
            if not part:
                continue
            if "*" in part:
                expanded.extend(glob.glob(part))
            elif Path(part).exists():
                expanded.append(part)
        return os.pathsep.join(expanded)
