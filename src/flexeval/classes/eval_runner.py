import logging
from datetime import datetime
from pathlib import Path

import dotenv
from peewee import SqliteDatabase

from flexeval import db_utils, dependency_graph
from flexeval.schema import EvalRun

logger = logging.getLogger(__name__)


class EvalRunner:
    """Class for maintaining database connection, logs, and run state
    Does not need to write anything to database itself.
    """

    database: SqliteDatabase

    def __init__(
        self,
        evalrun: EvalRun,
    ):
        self.evalrun: EvalRun = evalrun

        self.initialize_logger()
        self.add_file_logger()
        self.load_env()
        self.initialize_database()
        self.load_evaluation_settings()

    def initialize_logger(self, add_stream_handler: bool = False):
        """Configure the logger for this class.

        Args:
            add_stream_handler (bool, optional): If True, will add a stream handler at the INFO level. Defaults to False.
        """
        self.logger = logging.getLogger("FlexEval")
        self.logger.setLevel(logging.DEBUG)

        if add_stream_handler:
            # TODO this stream handler logic should probably be removed
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
        if self.evalrun.config.logs_path is None:
            logger.info("No log path specified, so not doing any file logging.")
            return
        logs_path = self.evalrun.config.logs_path
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
        log_filepath = logs_path / f"{current_date}_{self.evalrun.eval.name}.log"
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
        env_filepath = self.evalrun.config.env_filepath
        if env_filepath is not None and str(env_filepath).strip() != "":
            if not env_filepath.exists():
                raise ValueError(
                    f"Environment file not present at configured path '{env_filepath}'."
                )
            dotenv.load_dotenv(env_filepath, verbose=True)
            self.logger.debug(f"Finished loading .env file from '{env_filepath}'.")
        else:
            self.logger.debug(
                f"Skipping .env file loading as config env_filepath is '{env_filepath}'."
            )

    def get_database_path(self) -> Path:
        return self.evalrun.database_path

    def initialize_database(self):
        """Initializes database and tables. If config.clear_tables, then current contents of tables are dropped."""
        db_utils.initialize_database(
            self.evalrun.database_path, clear_tables=self.evalrun.config.clear_tables
        )

    def load_evaluation_settings(self):
        """This function parses our eval suite and puts it in the data structure we'll need
        for easy use at run-time.
        """
        # if the current eval has a 'config' entry, overwrite configuration options with its entries
        if (
            self.evalrun.eval.model_extra is not None
            and len(self.evalrun.eval.model_extra) > 0
        ):
            model_extra = self.evalrun.eval.model_extra
            self.logger.debug(
                f"Extra configuration keys provided in eval: {list(model_extra.keys())}"
            )
            for field_name in model_extra.keys():
                if hasattr(self.evalrun.config, field_name):
                    old_value = getattr(self.evalrun.config, field_name)
                    new_value = model_extra[field_name]
                    self.logger.info(
                        f"Updating configuration setting: '{field_name}'='{new_value}' (old='{old_value}')"
                    )
                    setattr(self.evalrun.config, field_name, new_value)
                else:
                    self.logger.warning(
                        f"Unknown configuration field '{field_name}' was ignored."
                    )

        # TODO verify that applying defaults is done solely by pydantic and this step is no longer necessary
        # apply defaults to the schema
        # self.eval = apply_defaults(schema=target_schema, data=self.eval)

        # convert into graph structure
        self.metrics_graph_ordered_list = dependency_graph.create_metrics_graph(
            self.evalrun.eval.metrics
        )
        # validate: completion function defined
        if len(self.metrics_graph_ordered_list) > 0:
            if self.evalrun.eval.grader_llm is None:
                self.logger.warning(
                    f"'{len(self.metrics_graph_ordered_list)}' metrics defined, but no grader LLM defined."
                )

    def shutdown_logging(self):
        # remove logging handler so we don't get repeat logs if we call run() twice
        handlers = self.logger.handlers[:]
        for handler in handlers:
            handler.close()
            self.logger.removeHandler(handler)
