import os
import re

from file_operations.file_ops import FileOperations


class JavaTestFileUpdater:
    COMMON_IMPORTS = [
        "import java.io.*;",
        "import java.lang.reflect.*;",
        "import java.math.*;",
        "import java.time.*;",
        "import java.util.*;",
        "import java.util.concurrent.*;",
        "import java.util.function.*;",
        "import java.util.stream.*;",
    ]

    @staticmethod
    def rename_class_declaration(content: str, suffix: str) -> str:
        return re.sub(r"(public\s+class\s+)(\w+)(\s*\{)", rf"\1\2{suffix}\3", content)

    @staticmethod
    def rename_constructor_usages(content: str, class_name: str, suffix: str) -> str:
        escaped = re.escape(class_name)
        pattern = rf"\b({escaped})(\b\s+\w+\s*=\s*new\s+)({escaped})(\s*\()"
        replacement = rf"\1{suffix}\2\3{suffix}\4"
        return re.sub(pattern, replacement, content)

    @staticmethod
    def ensure_common_imports(content: str) -> str:
        lines = content.splitlines()
        import_pattern = re.compile(r"^\s*import\s+[^;]+;\s*$")
        package_pattern = re.compile(r"^\s*package\s+[^;]+;\s*$")

        package_idx = None
        import_lines = []
        existing_imports = set()

        for idx, line in enumerate(lines):
            if package_pattern.match(line):
                package_idx = idx
            if import_pattern.match(line):
                import_lines.append(idx)
                existing_imports.add(line.strip())

        missing = [
            imp for imp in JavaTestFileUpdater.COMMON_IMPORTS if imp not in existing_imports
        ]
        if not missing:
            return content

        insert_idx = import_lines[-1] + 1 if import_lines else (
            package_idx + 1 if package_idx is not None else 0
        )

        new_lines = lines[:insert_idx] + missing + lines[insert_idx:]
        return "\n".join(new_lines)

    @staticmethod
    def prepare_test_file(
        file_path: str, suffix: str = "Augmented", is_driver: bool = False
    ) -> str:
        content = FileOperations.read_file(file_path)
        content = JavaTestFileUpdater.rename_class_declaration(content, suffix)
        content = JavaTestFileUpdater.ensure_common_imports(content)
        base, ext = os.path.splitext(file_path)
        new_file_path = f"{base}{suffix}{ext}"

        if ext != ".java":
            raise ValueError(f"File {file_path} is not a Java file.")

        if is_driver:
            class_name = os.path.basename(file_path).replace("Driver.java", "0")
            content = JavaTestFileUpdater.rename_constructor_usages(
                content, class_name, suffix
            )

        FileOperations.write_file(new_file_path, content)
        return new_file_path
