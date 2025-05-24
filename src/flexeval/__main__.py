import logging

from flexeval import runner, log_utils
from flexeval.cli import primary

logger = logging.getLogger(__name__)


def main():
    # Parse passed arguments
    parser = primary.get_parser()
    args = parser.parse_args()

    log_utils.set_up_logging()

    logger.debug("Command-line args: %s", str(args))

    # Evoke run()
    runner.run_from_args(**vars(args))


if __name__ == "__main__":
    main()
