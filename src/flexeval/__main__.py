import argparse
import logging

from flexeval import runner
from flexeval.cli import primary

logger = logging.getLogger(__name__)


def main():
    # Parse passed arguments
    parser = primary.get_parser()
    args = parser.parse_args()

    primary.set_up_logging()

    logger.debug("Command-line args: %s", str(args))

    # Evoke run()
    eval, config = primary.load_eval_and_config(args)
    runner.run(eval, config)


if __name__ == "__main__":
    main()
