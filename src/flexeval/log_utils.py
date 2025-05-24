import logging


def set_up_logging():
    # set up logging
    # TODO add option to silence logging or otherwise set level of verbosity
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d (%(funcName)s) - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
