import os
from pathlib import Path
import subprocess
from typing import Optional
from file_operations.file_ops import FileOperations
from subject.subject import Subject

DEFAULT_FRONTEND_TIMEOUT = 3600  # seconds
DEFAULT_INVARIANT_TIMEOUT = 3600  # seconds


class Daikon:

    def __init__(
        self,
        subject: Subject,
        driver: str,
        driver_fq_name: str,
        output_dir: str,
        front_end_timeout: int = DEFAULT_FRONTEND_TIMEOUT,
        invariant_timeout: int = DEFAULT_INVARIANT_TIMEOUT,
    ) -> None:
        self.subject = subject
        self.test_driver = driver
        self.test_driver_fq_name = driver_fq_name
        self.output_dir = output_dir
        self.front_end_timeout = front_end_timeout
        self.invariant_timeout = invariant_timeout

        # Use build/classes for Gradle projects, fallback to build/libs if it exists
        main_classes = os.path.join(
            subject.root_dir, "build", "classes", "java", "main"
        )
        test_classes = os.path.join(
            subject.root_dir, "build", "classes", "java", "test"
        )
        build_libs = os.path.join(subject.root_dir, "build", "libs", "*")
        self.subject_cp = os.pathsep.join([main_classes, test_classes, build_libs])

        # Include both project-specific libs and global libs in classpath
        project_libs = os.path.join(subject.root_dir, "libs", "*")
        self.cp_for_daikon = os.pathsep.join([project_libs, "libs/*", self.subject_cp])

        self.objs_file: Optional[str] = None

    def run_dyn_comp(self) -> None:
        Path(f"{self.output_dir}/{self.test_driver}.decls-DynComp").touch()
        try:
            cmd = [
                "java",
                "-cp",
                self.cp_for_daikon,
                "daikon.DynComp",
                self.test_driver_fq_name,
                "--output-dir",
                self.output_dir,
            ]
            subprocess.run(cmd, check=True, timeout=self.front_end_timeout)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Error running DynComp: {e}.")
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(
                "DynComp did not finish before the timeout "
                f"({self.front_end_timeout}s)."
            ) from e

    def run_chicory_dtrace_generation(self):
        self.objs_file = f"{self.output_dir}/{self.test_driver}-objects.xml"
        cmp_file = f"{self.output_dir}/{self.test_driver}.decls-DynComp"
        cmd = [
            "java",
            "-cp",
            self.cp_for_daikon,
            "daikon.Chicory",
            "--output-dir",
            self.output_dir,
            "--comparability-file",
            cmp_file,
            "--ppt-omit-pattern",
            f"{self.test_driver}.*",
            self.test_driver_fq_name,
            self.objs_file,
        ]
        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=self.front_end_timeout,
            )
        except subprocess.CalledProcessError as e:
            error_msg = "Error running Chicory DTrace generation.\n"
            error_msg += f"Command: {' '.join(cmd)}\n"
            error_msg += f"Return code: {e.returncode}\n"
            if e.stdout:
                error_msg += f"Stdout: {e.stdout}\n"
            if e.stderr:
                error_msg += f"Stderr: {e.stderr}\n"
            raise RuntimeError(error_msg)
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(
                "Chicory instrumentation exceeded the timeout "
                f"({self.front_end_timeout}s)."
            ) from e

    def run_invariant_checker(self, inv_gz_file: str) -> str:
        dtrace_file = f"{self.output_dir}/{self.test_driver}.dtrace.gz"
        try:
            cmd = [
                "java",
                "-Xmx8g",
                "-cp",
                self.cp_for_daikon,
                "daikon.tools.InvariantChecker",
                "--conf",
                "--serialiazed-objects",
                self.objs_file,
                inv_gz_file,
                dtrace_file,
            ]
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.DEVNULL,
                timeout=self.invariant_timeout,
            )
            FileOperations.move_file("invs.csv", self.output_dir)
            FileOperations.remove_file("invs_file.xml")
            return f"{self.output_dir}/invs.csv"
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Error running Invariant Checker: {e}")
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(
                "InvariantChecker took longer than the timeout "
                f"({self.invariant_timeout}s)."
            ) from e
