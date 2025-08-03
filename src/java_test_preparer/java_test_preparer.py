import os
import re

from file_handler.file_ops import FileHandler


class JavaTestPreparer:

    @staticmethod
    def rename_class_declaration(content: str, suffix: str) -> str:
        return re.sub(r"(public\s+class\s+)(\w+)(\s*\{)", rf"\1\2{suffix}\3", content)

    @staticmethod
    def rename_constructor_usages(content: str, class_name: str) -> str:
        escaped = re.escape(class_name)
        pattern = rf"\b({escaped})(\b\s+\w+\s*=\s*new\s+)({escaped})(\s*\()"
        replacement = r"\1Augmented\2\3Augmented\4"
        return re.sub(pattern, replacement, content)

    @staticmethod
    def prepare_test_file(
        file_path: str, suffix: str = "Augmented", is_driver: bool = False
    ) -> str:
        content = FileHandler.read_file(file_path)
        content = JavaTestPreparer.rename_class_declaration(content, suffix)
        base, ext = os.path.splitext(file_path)
        new_file_path = f"{base}{suffix}{ext}"

        if ext != ".java":
            raise ValueError(f"File {file_path} is not a Java file.")

        if is_driver:
            class_name = os.path.basename(file_path).replace("Driver.java", "0")
            content = JavaTestPreparer.rename_constructor_usages(content, class_name)

        FileHandler.write_file(new_file_path, content)
        return new_file_path
