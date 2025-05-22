import json
import logging
import io
import os
import sqlite3
import unittest
from datetime import datetime
from pathlib import Path
import importlib
import importlib.util
import jsonschema
import yaml
from peewee import SqliteDatabase

from flexeval import helpers, validate, compute_metrics
from flexeval.classes.dataset import Dataset
from flexeval.classes.eval_set_run import EvalSetRun
from flexeval.classes.message import Message
from flexeval.classes.metric import Metric
from flexeval.classes.thread import Thread
from flexeval.classes.tool_call import ToolCall
from flexeval.classes.turn import Turn
from flexeval.helpers import apply_defaults
from flexeval.schema import Config, Eval

logger = logging.getLogger(__name__)


class EvalRunner:
    """Class for maintaining database connection, logs, and run state
    Does not need to write anything to database itself.
    """

    database: SqliteDatabase
    eval_name: str

    def __init__(
        self,
        eval: Eval,
        config: Config,
    ):
        self.eval: Eval = eval
        self.config: Config = config

        self.initialize_logger()
        self.load_configuration()
        self.add_file_logger()
        self.validate_settings()
        self.initialize_database_connection()
        self.initialize_database_tables()
        self.load_evaluation_settings()

    def initialize_logger(self, add_stream_handler: bool = False):
        # Configure the logger
        self.logger = logging.getLogger("FlexEval")
        self.logger.setLevel(logging.DEBUG)

        if add_stream_handler:
            # Create a console handler for lower level messages to output to console
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)

            # Create a formatter and set it for the handlers
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            ch.setFormatter(formatter)

            # Add the handlers to the logger
            self.logger.addHandler(ch)

    def add_file_logger(self):
        if (
            "logs_path" not in self.configuration
            or self.configuration["logs_path"] is None
            or str(self.configuration["logs_path"]).strip() == ""
        ):
            logger.debug("No logs_path defined, so not using a file logger.")
            return

        # Get the current date to use in the filename
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Create a file handler that logs debug and higher level messages to a date-based file
        logs_path = Path(self.configuration["logs_path"])
        logs_path.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(
            logs_path / f"{current_date}_{self.eval_name}.log",
        )
        fh.setLevel(logging.DEBUG)

        # Create a formatter and set it for the handlers
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

    def validate_settings(self):
        self.logger.debug("Verifying configuration")
        # Locate the tests
        suite = unittest.defaultTestLoader.loadTestsFromModule(validate)
        # Run the tests and capture the results
        validation_stream = io.StringIO()
        result = unittest.TextTestRunner(stream=validation_stream).run(suite)
        # Check if validation succeeded
        if not result.wasSuccessful():
            validation_output = validation_stream.getvalue()
            error_message = f"Something is wrong with your configuration. {len(result.failures)} validation failures and {len(result.errors)} runtime errors checking {result.testsRun} tests. See report below:\n{validation_output}"
            logger.error(error_message)
            self.logger.error(error_message)
            raise ValueError(f"Bad configuration for eval '{self.eval_name}'.")

    def get_database_path(self) -> str:
        return self.configuration["database_path"]

    def initialize_database_connection(self):
        """In peewee, each object has its own database connection
        This is fine - so we'll just make the path available here
        """
        # os.environ["DATABASE_PATH"] = self.configuration["database_path"]

        # also set up SQLite so it's less likely to error when there are multiple writes
        with sqlite3.connect(
            self.configuration["database_path"], check_same_thread=False
        ) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")  # Enable Write-Ahead Logging

    def initialize_database_tables(self):
        """Initializes database tables. If config.clear_tables, then current contents of tables are dropped."""
        database_path = self.configuration["database_path"]
        for cls in [EvalSetRun, Dataset, Thread, Turn, Message, ToolCall, Metric]:
            cls.initialize_database(database_path, clear_table=self.config.clear_tables)

    def load_evaluation_settings(self):
        """This function parses our eval suite and puts it in the data structure we'll need
        for easy use at run-time
        """

        with open(self.configuration["evals_path"]) as file:
            self.all_evaluations = yaml.safe_load(file)
            if self.eval_name not in self.all_evaluations:
                raise ValueError(
                    f"You specified an evaluation called `{self.eval_name}` in the file `{os.path.abspath(self.configuration.get('evals_path'))}`. Available evaluations are `{list(self.all_evaluations.keys())}`"
                )
            self.eval = self.all_evaluations.get(self.eval_name)

        # if the current eval has a 'config' entry, overwrite configuration options with its entries
        if "config" in self.eval:
            for k, v in self.eval.get("config", {}).items():
                if k in self.configuration:
                    self.logger.info(
                        f"Updating configuration setting: {k}={v} (old={self.configuration.get(k,'unset')})"
                    )
                    self.configuration[k] = v
        if self.evals_path is not None:
            if str(self.evals_path) != str(self.configuration["evals_path"]):
                self.logger.info(
                    f"Updating configuration setting: evals_path={self.evals_path}"
                )
                self.configuration["evals_path"] = self.evals_path
            else:
                self.logger.debug(
                    f"evals_path specified, but it's not different than the value provided in the configuration: {self.evals_path}"
                )

        # Validate that the schema meets the required structure
        with open(self.configuration["eval_schema_path"], "r") as infile:
            target_schema = json.load(infile)
        # has already been validated - probably don't need to do this
        jsonschema.validate(schema=target_schema, instance=self.eval)

        # apply defaults to the schema
        self.eval = apply_defaults(schema=target_schema, data=self.eval)
        # convert into graph structure
        self.metrics_graph_ordered_list = helpers.create_metrics_graph(
            self.eval["metrics"]
        )

    def shutdown_logging(self):
        # remove logging handler so we don't get repeat logs if we call run() twice
        handlers = self.logger.handlers[:]
        for handler in handlers:
            handler.close()
            self.logger.removeHandler(handler)

    def get_metric_computer(self):
        function_modules = self.configuration.get("function_modules", [])
        if len(function_modules) > 0:
            # convert from string module names or filepaths to Python modules
            actual_modules = []
            for i, function_module in enumerate(function_modules):
                try:
                    module = importlib.import_module(function_module)

                except ModuleNotFoundError:
                    try:
                        spec = importlib.util.spec_from_file_location(
                            f"function_module_{i}", function_module
                        )
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                    except Exception as ex:
                        raise ValueError(
                            f"Failed to load function module specified by {function_module}."
                        )
                actual_modules.append(module)
            function_modules = actual_modules
        include_default_functions = self.configuration.get(
            "include_default_functions", True
        )
        return compute_metrics.MetricComputer(
            function_modules, include_default_functions
        )
