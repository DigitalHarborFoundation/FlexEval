import argparse
import logging

from flexeval.schema import Eval, Config
from flexeval.io.parsers import yaml_parser


def set_up_logging():
    # set up logging
    # TODO add option to silence logging or otherwise set level of verbosity
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d (%(funcName)s) - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--eval_name",
        type=str,
        help="Which eval set in evals.yaml you want to run",
    )
    parser.add_argument(
        "--evals_path",
        type=str,
        help="Path to the evaluation file evals.yaml you want to run. Default is src/flexeval/configuration/evals.yaml",
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
        default="src/flexeval/config.yaml",
    )
    return parser
