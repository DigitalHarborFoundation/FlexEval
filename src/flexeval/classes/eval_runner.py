import importlib
import importlib.util
import io
import json
import logging
import os
import sqlite3
import types
import unittest
from datetime import datetime
from pathlib import Path

import dotenv
from peewee import SqliteDatabase

from flexeval import compute_metrics, helpers, validate
from flexeval.classes.dataset import Dataset
from flexeval.classes.eval_set_run import EvalSetRun
from flexeval.classes.message import Message
from flexeval.classes.metric import Metric
from flexeval.classes.thread import Thread
from flexeval.classes.tool_call import ToolCall
from flexeval.classes.turn import Turn
from flexeval.schema import Config, Eval

logger = logging.getLogger(__name__)


class EvalRunner:
    """Class for maintaining database connection, logs, and run state
    Does not need to write anything to database itself.
    """

    database: SqliteDatabase

    def __init__(
        self,
        eval: Eval,
        config: Config,
    ):
        self.eval: Eval = eval
        self.config: Config = config

        self.initialize_logger()
        self.add_file_logger()
        self.load_env()
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
        if self.config.logs_path is None:
            logger.info(f"No log path specified, so not doing any file logging.")
            return
        logs_path = self.config.logs_path
        if logs_path.is_file():
            raise ValueError(
                f"Config logs_path expects a directory, but was set to existing file '{logs_path}'."
            )
        elif not logs_path.exists():
            if logs_path.suffix != "":
                logger.warning(
                    f"Creating logs_path '{logs_path}' as a directory, despite apparent suffix '{logs_path.suffix}'."
                )
            logs_path.mkdir(parents=True, exist_ok=True)

        # Get the current date to use in the filename
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Create a file handler that logs debug and higher level messages to a date-based file
        log_filepath = logs_path / f"{current_date}_{self.eval.name}.log"
        fh = logging.FileHandler(log_filepath)
        fh.setLevel(logging.DEBUG)

        # Create a formatter and set it for the handlers
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        self.logger.info(f"Started logging to log file '{log_filepath}'.")

    def load_env(self):
        if (
            self.config.env_filepath is not None
            and self.config.env_filepath.strip() != ""
        ):
            if not self.config.env_filepath.exists():
                raise ValueError(
                    f"Environment file not present at configured path '{self.config.env_filepath}'."
                )
            dotenv.load_dotenv(self.config.env_filepath, verbose=True)
            self.logger.debug(
                f"Finished loading .env file from '{self.config.env_filepath}'."
            )
        else:
            self.logger.debug(
                f"Skipping .env file loading as config env_filepath is '{self.config.env_filepath}'."
            )

    def validate_settings(self):
        self.logger.debug("Attempting to verify configuration.")
        os.environ["FLEXEVAL_VALIDATE_CONFIG_JSON"] = self.config.model_dump_json()
        os.environ["FLEXEVAL_VALIDATE_EVAL_JSON"] = self.eval.model_dump_json()
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
            raise ValueError(f"Bad configuration for eval '{self.eval.name}'.")
        self.logger.debug("Verified configuration successfully.")

    def get_database_path(self) -> Path:
        return self.config.database_path

    def initialize_database_connection(self):
        """In peewee, each object has its own database connection
        This is fine - so we'll just make the path available here
        """
        # set up SQLite so it's less likely to error when there are multiple writes
        with sqlite3.connect(
            str(self.get_database_path()), check_same_thread=False
        ) as conn:
            # Enable Write-Ahead Logging
            conn.execute("PRAGMA journal_mode=WAL;")

    def initialize_database_tables(self):
        """Initializes database tables. If config.clear_tables, then current contents of tables are dropped."""
        database_path = self.get_database_path()
        for cls in [EvalSetRun, Dataset, Thread, Turn, Message, ToolCall, Metric]:
            cls.initialize_database(database_path, clear_table=self.config.clear_tables)

    def load_evaluation_settings(self):
        """This function parses our eval suite and puts it in the data structure we'll need
        for easy use at run-time
        """
        # if the current eval has a 'config' entry, overwrite configuration options with its entries
        if self.eval.config is not None:
            for field_name in self.eval.config.model_fields_set:
                if hasattr(self.config, field_name):
                    value = getattr(self.eval.config, field_name)
                    old_value = getattr(self.config, field_name, "unset")
                    self.logger.info(
                        f"Updating configuration setting: {field_name}={value} (old={old_value})"
                    )
                    setattr(self.config, field_name, value)
                else:
                    # TODO is this the expected behavior here?
                    self.logger.warning(
                        f"Avoiding config override for field {field_name} because it's not set in the config."
                    )

        # TODO verify that applying defaults is done solely by pydantic and this step is no longer necessary
        # apply defaults to the schema
        # self.eval = apply_defaults(schema=target_schema, data=self.eval)

        # convert into graph structure
        self.metrics_graph_ordered_list = helpers.create_metrics_graph(
            self.eval.metrics
        )

    def shutdown_logging(self):
        # remove logging handler so we don't get repeat logs if we call run() twice
        handlers = self.logger.handlers[:]
        for handler in handlers:
            handler.close()
            self.logger.removeHandler(handler)

    def get_metric_computer(self):
        function_modules = (
            self.config.function_modules
            if self.config.function_modules is not None
            else []
        )
        # convert from string module names or filepaths to Python modules
        actual_modules = []
        for i, function_module in enumerate(function_modules):
            if isinstance(function_module, types.ModuleType):
                # already a module
                actual_modules.append(function_module)
                continue
            try:
                module = importlib.import_module(function_module)

            except ModuleNotFoundError as module_not_found:
                try:
                    spec = importlib.util.spec_from_file_location(
                        f"function_module_{i}", function_module
                    )
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                except Exception as module_not_loaded:
                    raise ValueError(
                        f"Failed to load function module specified by {function_module}. (module not found: {module_not_found}, and failed to load from file location: {module_not_loaded})"
                    )
            actual_modules.append(module)
        return compute_metrics.MetricComputer(
            actual_modules, self.config.include_default_functions
        )
