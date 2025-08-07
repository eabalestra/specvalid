import subprocess
from subject.subject import Subject


class Daikon:

    def __init__(
        self, subject: Subject, driver: str, driver_fq_name: str, output_dir: str
    ) -> None:
        self.subject = subject
        self.test_driver = driver
        self.test_driver_fq_name = driver_fq_name
        self.output_dir = output_dir
        self.subject_cp = f"{subject.root_dir}/build/libs/*"
        self.cp_for_daikon = f"libs/*:{self.subject_cp}"

    def run_dyn_comp(self) -> None:
        open(f"{self.output_dir}/{self.test_driver}.decls-DynComp", "w").close()
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
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Error running DynComp: {e}.")

    def run_chicory_dtrace_generation(self):
        objs_file = f"{self.output_dir}/{self.test_driver}-objects.xml"
        cmp_file = f"{self.output_dir}/{self.test_driver}.decls-DynComp"
        try:
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
                objs_file,
            ]
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Error running Chicory DTrace generation: {e}")
