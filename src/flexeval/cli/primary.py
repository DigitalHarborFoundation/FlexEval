import argparse


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--eval-name",
        type=str,
        help="Which eval set in evals.yaml you want to run",
    )
    parser.add_argument(
        "--evals-path",
        type=str,
        help="Path to the evaluation file evals.yaml you want to run. Default is src/flexeval/configuration/evals.yaml",
    )
    parser.add_argument(
        "--clear-tables",
        action="store_true",
        help="Set this flag to drop existing tables in the results database before running. Useful during development.",
    )
    parser.add_argument(
        "--config-path",
        type=str,
        help="Which config file to use",
        default="src/flexeval/config.yaml",
    )
    # TODO add as CLI options all fields in Config
    return parser
