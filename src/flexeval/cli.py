"""CLI commands."""

import logging
from pathlib import Path
from typing import Annotated

import typer

from flexeval import db_utils, log_utils, runner
from flexeval.io.parsers import yaml_parser
from flexeval.metrics import access

logger = logging.getLogger(__name__)


def global_callback(
    ctx: typer.Context,
    log_level: Annotated[
        log_utils.LogLevel, typer.Option(help="Log level to use.", case_sensitive=False)
    ] = log_utils.LogLevel.INFO.value,
):
    """FlexEval offers a number of CLI commands for convenience."""
    log_utils.set_up_logging(log_utils.LogLevel.get_logging_constant(log_level.value))


app = typer.Typer(callback=global_callback)


@app.command(no_args_is_help=True)
def run(
    eval_run_yaml_path: Annotated[
        Path, typer.Argument(help="YAML file specifying the Eval Run.")
    ],
):
    """Run FlexEval using the given YAML Eval Run configuration."""
    eval_run = yaml_parser.load_eval_run_from_yaml(eval_run_yaml_path)
    runner.run(eval_run)


@app.command(no_args_is_help=True)
def summarize_metrics(
    eval_run_yaml_path: Annotated[
        Path | None,
        typer.Argument(
            help="YAML file specifying the Eval Run.",
            exists=True,
            dir_okay=False,
        ),
    ] = None,
    database_path: Annotated[
        Path | None,
        typer.Option(help="Database path.", exists=True, dir_okay=False),
    ] = None,
):
    """Print a summary of computed metrics."""
    if eval_run_yaml_path is not None:
        if database_path is not None:
            logger.warning(
                "Ignoring database_path since eval_run_yaml_path is provided."
            )
        eval_run = yaml_parser.load_eval_run_from_yaml(eval_run_yaml_path)
        database_path = eval_run.database_path

    if database_path is None:
        raise ValueError("Must provide an Eval Run or a database path.")
    db_utils.initialize_database(database_path)
    counts = access.count_dict_values(access.get_all_metrics())
    print("Summary of metric value counts:")
    for key, counter in counts.items():
        print("  " + key)
        for value, count in counter.most_common(5):
            value = str(value)
            display_limit = 50
            if len(value) > display_limit:
                value = value[: display_limit - 3].replace("\n", "\\n") + "..."
            print(f"    {value}: {count}")


@app.command(no_args_is_help=True)
def run_eval_by_name(
    input_data: Annotated[list[Path], typer.Option(help="Input data filepaths.")],
    database_path: Annotated[Path, typer.Option(help="Output database path.")],
    eval_name: str,
    evals_path: Path,
    config_path: Path,
    clear_tables: bool = False,
):
    """Run an eval by name."""
    runner.run_from_name_args(
        input_data,
        database_path,
        eval_name,
        config_path,
        evals_path,
        clear_tables=clear_tables,
    )


def main():
    app()


if __name__ == "__main__":
    main()
