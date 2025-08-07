from utils.utils import Utils


class JavaTestDriver:
    def __init__(self, test_driver_path: str) -> None:
        self.test_driver_path = test_driver_path

    def get_package_name(self) -> str:
        return Utils.get_java_package_from_path(self.test_driver_path)
