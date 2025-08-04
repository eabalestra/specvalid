import logging


class Logger:
    def __init__(self, output_path) -> None:
        self.output_path = output_path

        logger_name = f"logger_{abs(hash(output_path))}"
        self.logger = logging.getLogger(logger_name)

        if self.logger.handlers:
            self.logger.handlers.clear()

        self.logger.setLevel(logging.DEBUG)

        file_handler = logging.FileHandler(output_path, mode="w")
        file_handler.setLevel(logging.DEBUG)

        formatter = logging.Formatter("%(levelname)s:%(name)s:%(message)s")
        file_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)

        # Prevent propagation to avoid duplicate logs
        self.logger.propagate = False

    def log(self, message: str) -> None:
        self.logger.info(message)

    def log_error(self, message: str) -> None:
        self.logger.error(message)

    def log_warning(self, message: str) -> None:
        self.logger.warning(message)

    def log_debug(self, message: str) -> None:
        self.logger.debug(message)

    def close(self) -> None:
        # Close all handlers for this specific logger
        for handler in self.logger.handlers:
            handler.close()
            self.logger.removeHandler(handler)
