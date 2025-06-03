import logging


def set_up_logging(log_level: int = logging.INFO):
    # set up logging
    # TODO add option to silence logging or otherwise set level of verbosity
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d (%(funcName)s) - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
