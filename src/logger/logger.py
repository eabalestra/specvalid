import logging


class Logger:
    def __init__(self, output_path) -> None:
        logging.basicConfig(filename=output_path,
                            level=logging.DEBUG,
                            filemode='w')
        self.logger = logging.getLogger(__name__)

    def log(self, message: str) -> None:
        self.logger.info(message)

    def log_error(self, message: str) -> None:
        self.logger.error(message)

    def log_warning(self, message: str) -> None:
        self.logger.warning(message)

    def log_debug(self, message: str) -> None:
        self.logger.debug(message)

    def close(self) -> None:
        logging.shutdown()
