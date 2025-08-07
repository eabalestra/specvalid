class Utils:
    def __init__(self):
        pass

    @staticmethod
    def get_java_package_from_path(file_path: str) -> str:
        parts = file_path.split("/java/")
        if len(parts) > 1:
            result = parts[1].split("/")
            return ".".join(result[:-1]).replace("/", ".")
        return ""
