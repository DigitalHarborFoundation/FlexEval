"""Logging utilities."""

import enum
import logging


class LogLevel(str, enum.Enum):
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"

    @classmethod
    def get_logging_constant(cls, level_str: str) -> int:
        if level_str == cls.CRITICAL.value:
            return logging.CRITICAL
        elif level_str == cls.ERROR.value:
            return logging.ERROR
        elif level_str == cls.WARNING.value:
            return logging.WARNING
        elif level_str == cls.INFO.value:
            return logging.INFO
        elif level_str == cls.DEBUG.value:
            return logging.DEBUG


def set_up_logging(log_level: int = logging.INFO):
    # set up logging
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d (%(funcName)s) - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
