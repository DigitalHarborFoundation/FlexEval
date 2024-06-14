import logging
from datetime import datetime
from peewee import *
import yaml
import unittest
import os
from pathlib import Path
import sys
import sqlite3
import json
import jsonschema
import helpers

from classes.EvalSetRun import EvalSetRun
from classes.Dataset import Dataset
from classes.DatasetRow import DatasetRow
from classes.Turn import Turn
from classes.TurnMetric import TurnMetric
from helpers import apply_defaults


class EvalRunner(Model):
    """Class for maintaining database connection, logs, and run state
    Does not need to write anything to database itself.
    """

    database: SqliteDatabase
    eval_name: str

    def __init__(self, eval_name: str, config_path: str, evals_path: str = None):

        self.eval_name = eval_name
        self.config_path = config_path
        self.evals_path = evals_path

        self.initialize_logger()
        self.load_configuration()
        self.add_file_logger()
        self.validate_settings()
        self.initialize_database_connection()
        self.initialize_database_tables()
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
        fh = logging.FileHandler(
            Path(self.configuration["logs_path"])
            / f"{current_date}_{self.eval_name}.log",
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
        # set args

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

    def initialize_database_tables(self):
        """Initializes database tables"""
        for cls in [EvalSetRun, Dataset, DatasetRow, Turn, TurnMetric]:
            cls.initialize_database()
            db = cls._meta.database
            db.connect()
            # TODO - remove this once the schema is finalized!!
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
            assert (
                self.eval_name in self.all_evaluations
            ), f"You specified a evaluation called `{self.eval_name}` in the file `{os.path.abspath(self.configuration.get('evals_path'))}`. Available evaluations are `{list(self.all_evaluations.keys())}`"
            self.eval = self.all_evaluations.get(self.eval_name)

        # if the current eval has a 'config' entry, overwrite configuration options with its entries
        if "config" in self.eval:
            for k, v in self.eval.get("config", {}).items():
                if k in self.configuration:
                    self.logger.info(f"Updating configuration setting: {k}={v}")
                    self.configuration[k] = v
        if self.evals_path is not None:
            self.logger.info(
                f"Updating configuration setting: evals_path={self.evals_path}"
            )
            self.configuration["evals_path"] = self.evals_path

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
