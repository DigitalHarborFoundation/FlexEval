import logging
from typing import Literal, Annotated
import typer
from pathlib import Path

from flexeval import runner, log_utils

logger = logging.getLogger(__name__)


app = typer.Typer()


def run_eval(
    eval_run: Annotated[
        Path, typer.Argument(help="YAML file specifying the execution.")
    ],
):
    pass


@app.command(no_args_is_help=True)
def run_eval_by_name(
    input_data: Annotated[list[Path], typer.Option(help="Input data filepaths.")],
    database_path: Annotated[Path, typer.Option(help="Output database path.")],
    eval_name: str,
    evals_path: Path,
    config_path: Path,
    clear_tables: bool = False,
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO",
):
    log_level = getattr(logging, log_level)

    log_utils.set_up_logging(log_level=log_level)
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
