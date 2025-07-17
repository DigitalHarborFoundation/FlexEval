import unittest

from flexeval import completions, run_utils
from flexeval.classes import eval_runner
from flexeval.schema import config_schema, eval_schema, evalrun_schema


def build_evalsetrun(metrics: eval_schema.Metrics):
    data_sources = [evalrun_schema.FileDataSource(path="tests/data/simple.jsonl")]
    eval = eval_schema.Eval(
        do_completion=True,
        completion_llm=eval_schema.CompletionLlm(
            function_name="litellm_completion",
            kwargs={"model": "gpt-4o-mini", "mock_response": "test_completions"},
        ),
    )
    eval_run = evalrun_schema.EvalRun(
        data_sources=data_sources,
        database_path="tests/data/test_completions.db",
        eval=eval,
        config=config_schema.Config(clear_tables=True),
    )

    # build an EvalRunner and an EvalSetRun
    runner = eval_runner.EvalRunner(eval_run)
    evalsetrun = run_utils.build_eval_set_run(runner)

    # build datasets
    run_utils.build_datasets(runner, evalsetrun)
    for dataset in evalsetrun.datasets:
        dataset.load_data()

    return evalsetrun, runner


class TestCompletions(unittest.TestCase):
    def test_get_completion_function(self):
        expected_response = "test_get_completion_function"
        completion_llm = eval_schema.CompletionLlm(
            function_name="litellm_completion",
            kwargs={"model": "gpt-4o-mini", "mock_response": expected_response},
        )
        completion_function = completions.get_completion_function(completion_llm)
        response = completion_function([], **completion_llm.kwargs)
        self.assertEqual(
            response["choices"][0]["message"]["content"], expected_response
        )
