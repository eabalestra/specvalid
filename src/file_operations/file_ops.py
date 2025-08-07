import os
import shutil


class FileOperations:
    @staticmethod
    def read_file(path: str) -> str:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def write_file(path: str, content: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    @staticmethod
    def move_file(src: str, dest: str) -> None:
        shutil.move(src, dest)

    @staticmethod
    def remove_file(path: str) -> None:
        try:
            os.remove(path)
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {path}")
