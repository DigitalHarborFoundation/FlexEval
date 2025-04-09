import argparse
import logging

from flexeval import runner

logger = logging.getLogger(__name__)


def main():
    ################################################################################
    ## Parse inputs and load config files
    ################################################################################
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--eval_name",
        type=str,
        help="Which eval set in evals.yaml you want to run",
    )
    parser.add_argument(
        "--evals_path",
        type=str,
        help="Path to the evaluation file evals.yaml you want to run. Deafult is configuration/evals.yaml.",
    )
    parser.add_argument(
        "--clear_tables",
        action="store_true",
        help="Set this flag to drop existing tables in the results database before running. Useful during development.",
    )
    parser.add_argument(
        "--config_path",
        type=str,
        help="Which config file to use",
        default="config.yaml",
    )

    # Parse passed arguments
    args = parser.parse_args()

    # set up logging
    # TODO add option to silence logging or otherwise set level of verbosity
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d (%(funcName)s) - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.debug("Command-line args: %s", str(args))

    # Evoke run()
    runner.run(**vars(args))


if __name__ == "__main__":
    main()
