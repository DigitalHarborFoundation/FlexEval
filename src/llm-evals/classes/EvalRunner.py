import logging
from datetime import datetime
from peewee import *
import yaml
import unittest
import os
from pathlib import Path
import sys
import sqlite3


from classes.EvalSetRun import EvalSetRun
from classes.Dataset import Dataset
from classes.DatasetRow import DatasetRow
from classes.Turn import Turn
from classes.TurnMetric import TurnMetric


class EvalRunner(Model):
    """Class for maintaining database connection, logs, and run state
    Does not need to write anything to database itself.
    """

    database: SqliteDatabase
    eval_name: str

    def __init__(self, eval_name: str, config_filename: str):

        self.eval_name = eval_name
        self.config_filename = config_filename

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
        with open(self.config_filename) as file:
            self.configuration = yaml.safe_load(file)

    def validate_settings(self):

        self.logger.debug("Verifying configuration")
        # Locate the tests
        suite = unittest.defaultTestLoader.discover(
            "tests/", pattern="verify_installation.py"
        )
        # set args
        os.environ["CONFIG_FILENAME"] = self.config_filename
        # Run the tests and capture the results
        result = unittest.TextTestRunner().run(suite)
        print(result)
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

    def validate_dataset(self, filename, rows):
        for ix, row in enumerate(rows):
            assert (
                "input" in row
            ), f"Dataset {filename}, row {ix+1} does not contain an input key!"
            assert isinstance(
                row["input"], list
            ), f"The `input` key for dataset {filename}, row {ix+1} does not map to a list!"

            for entry_ix, entry in enumerate(row["input"]):
                assert (
                    "role" in entry
                ), f"Entry {entry_ix+1} in the `input` key for dataset {filename}, row {ix+1} does not contain a `role` key!"
                assert (
                    "content" in entry
                ), f"Entry {entry_ix+1} in the `input` key for dataset {filename}, row {ix+1} does not contain a `content` key!"
                assert entry["role"] in [
                    "user",
                    "assistant",
                    "tool",
                    "system",
                ], f"`user` key in entry {entry_ix+1} in the `input` key for dataset {filename}, row {ix+1} must be one of `tool`,`user`,`assistant`! You have `{entry['role']}`."

    # TODO - assert that 'ideals' is a dict
    # TODO - assert that each key in ideals is an eval we'll be running
