import json
import logging
import os
import sqlite3
import sys
import unittest
from datetime import datetime
from pathlib import Path

import jsonschema
import yaml
from peewee import *

from flexeval import helpers
from flexeval.classes.dataset import Dataset
from flexeval.classes.eval_set_run import EvalSetRun
from flexeval.classes.message import Message
from flexeval.classes.metric import Metric
# from flexeval.classes.TurnMetric import TurnMetric
from flexeval.classes.thread import Thread
from flexeval.classes.tool_call import ToolCall
# from flexeval.classes.DatasetRow import DatasetRow
from flexeval.classes.turn import Turn
from flexeval.helpers import apply_defaults


class EvalRunner(Model):
    """Class for maintaining database connection, logs, and run state
    Does not need to write anything to database itself.
    """

    database: SqliteDatabase
    eval_name: str

    def __init__(
        self,
        eval_name: str,
        config_path: str | Path,
        evals_path: str | None = None,
        clear_tables: bool = False,
    ):

        self.eval_name = eval_name
        self.config_path = config_path
        self.evals_path = evals_path

        self.initialize_logger()
        self.load_configuration()
        self.add_file_logger()
        self.validate_settings()
        self.initialize_database_connection()
        self.initialize_database_tables(clear_tables)
        self.load_evaluation_settings()

    def initialize_logger(self):
        # Configure the logger
        self.logger = logging.getLogger("FlexEval")
        self.logger.setLevel(logging.DEBUG)

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

    def load_configuration(self):
        """Load configuration file
        This file contains information about relative paths, etc
        It is NOT the file that specifies the evaluation
        """

        # Load configs
        with open(self.config_path) as file:
            self.configuration = yaml.safe_load(file)

    def validate_settings(self):

        self.logger.debug("Verifying configuration")
        # Locate the tests
        suite = unittest.defaultTestLoader.discover(
            "tests/", pattern="verify_installation.py"
        )
        # set args in environment so they're available in the test
        os.environ["CONFIG_FILENAME"] = self.config_path
        os.environ["EVALUATION_NAME"] = self.eval_name
        # Run the tests and capture the results
        os.getenv("CONFIG_FILENAME")
        result = unittest.TextTestRunner().run(suite)
        # Check if there were any failures or errors
        test_failed = not result.wasSuccessful()
        if test_failed:
            print(
                "Something is wrong with your configuration. See error messages for details. Exiting."
            )
            sys.exit()

    def initialize_database_connection(self):
        """In peewee, each object has its own database connection
        This is fine - so we'll just make the path available here
        """
        os.environ["DATABASE_PATH"] = self.configuration["database_path"]

        # also set up SQLite so it's less likely to error when there are multiple writes
        with sqlite3.connect(
            self.configuration["database_path"], check_same_thread=False
        ) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")  # Enable Write-Ahead Logging

    def initialize_database_tables(self, clear_tables: bool = False):
        """Initializes database tables. If clear_tables, then current contents of tables are dropped."""
        for cls in [EvalSetRun, Dataset, Thread, Turn, Message, ToolCall, Metric]:
            cls.initialize_database()
            db = cls._meta.database
            db.connect()
            if clear_tables:
                db.drop_tables([cls])
            db.create_tables([cls], safe=False)  # can alter tables if needed

    # def connect_to_db(self):
    #     return SqliteDatabase(os.environ["DATABASE_PATH"])

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
            if self.evals_path != self.configuration["evals_path"]:
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
