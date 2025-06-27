import pathlib
import tempfile
import unittest.mock

import dotenv

from flexeval import run_utils, runner
from flexeval.classes.eval_runner import EvalRunner
from flexeval.schema import Config, Eval, EvalRun, FileDataSource, GraderLlm, Metrics


class TempPathMixin:
    def setUp(self):
        super().setUp()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = pathlib.Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()
        super().tearDown()


class DotenvMixin:
    def setUp(self):
        super().setUp()
        # TODO we could restore os.environ after running this
        dotenv.load_dotenv("tests/resources/unittest.env", override=True)

    def tearDown(self):
        super().tearDown()


class PatchOpenAIMixin:
    def setUp(self):
        super().setUp()
        patcher = unittest.mock.patch("")
        self.mock_create = patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        super().tearDown()


class EvalRunMixin:
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        data_sources = [FileDataSource(path="tests/data/simple.jsonl")]
        database_path = "tests/data/unittest.db"
        cls.config = Config(
            logs_path="tests/unit/logs/",
            clear_tables=True,
            raise_on_completion_error=True,
            raise_on_metric_error=True,
        )
        cls.eval = Eval(
            metrics=getattr(cls, "metrics", Metrics()),
            grader_llm=GraderLlm(
                function_name="echo_completion", kwargs={"response": "YES"}
            ),
        )
        cls.eval_run = EvalRun(
            data_sources=data_sources,
            database_path=database_path,
            eval=cls.eval,
            config=cls.config,
        )


class EvalRunnerCompleteMixin(EvalRunMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # run a full evaluation
        cls.runner = runner.run(cls.eval_run)


class EvalSetRunMixin(EvalRunMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # build an EvalRunner and an EvalSetRun
        cls.runner = EvalRunner(cls.eval_run)
        cls.evalsetrun = run_utils.build_eval_set_run(cls.runner)


class DatasetsMixin(EvalSetRunMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # build datasets
        run_utils.build_datasets(cls.runner, cls.evalsetrun)
        for dataset in cls.evalsetrun.datasets:
            dataset.load_data()
