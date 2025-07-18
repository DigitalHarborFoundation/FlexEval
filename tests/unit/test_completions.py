import unittest

from flexeval import completions, run_utils, classes
from flexeval.classes import eval_runner
from flexeval.schema import config_schema, eval_schema, evalrun_schema


def build_evalsetrun(mock_response: str):
    data_sources = [evalrun_schema.FileDataSource(path="tests/data/simple.jsonl")]
    eval = eval_schema.Eval(
        do_completion=True,
        completion_llm=eval_schema.CompletionLlm(
            function_name="litellm_completion",
            kwargs={
                "model": "gpt-4o-mini",
                "mock_response": mock_response,
            },
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

    def test_get_completions(self):
        mock_response = "test_get_completions"
        for n_workers in [1, 2]:
            evalsetrun, runner = build_evalsetrun(mock_response)
            runner.evalrun.config.max_workers = n_workers
            for thread in evalsetrun.threads:
                self.assertEqual(
                    len(thread.turns),
                    3,
                    "Expected 3 turns in each conversation before completions.",
                )
            completions.get_completions(runner.evalrun, evalsetrun)

            for thread in evalsetrun.threads:
                self.assertEqual(
                    len(thread.turns),
                    4,
                    "Expected 4 turns in each conversation after completions.",
                )
                self.assertEqual(
                    thread.turns.select()
                    .order_by(classes.turn.Turn.index_in_thread.asc())
                    .first()
                    .index_in_thread,
                    0,
                    "First turn in each thread should have index_in_thread == 0 by convention.",
                )
                turn = (
                    thread.turns.select()
                    .order_by(classes.turn.Turn.index_in_thread.desc())
                    .first()
                )
                self.assertEqual(turn.index_in_thread, 3)
                self.assertEqual(len(turn.messages), 1)
                message = turn.messages.first()
                self.assertEqual(message.content, mock_response)
                self.assertTrue(message.is_flexeval_completion)
