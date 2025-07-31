import unittest

from pydantic import ValidationError

from flexeval.schema import config_schema, eval_schema, evalrun_schema, rubric_schema


class TestSchema(unittest.TestCase):
    def test_eval(self):
        model = eval_schema.Eval()
        self.assertIsNotNone(model.model_dump())

    def test_config(self):
        model = config_schema.Config()
        self.assertIsNotNone(model.model_dump())

    def test_rubric(self):
        with self.assertRaises(ValidationError):
            rubric_schema.Rubric(prompt="", choice_scores={})
        model = rubric_schema.Rubric(prompt="", choice_scores={"a": 0, "b": 1})
        self.assertIsNotNone(model.model_dump())

    def test_evalrun(self):
        data_sources = [
            evalrun_schema.FileDataSource(path="tests/resources/test_dataset.jsonl")
        ]
        model = evalrun_schema.EvalRun(
            data_sources=data_sources,
            eval=eval_schema.Eval(),
            config=config_schema.Config(),
        )
        self.assertIsNotNone(model.model_dump())
