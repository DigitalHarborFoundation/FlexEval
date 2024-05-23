import random
import inspect
import evals
import evals.metrics
import evals.record
from configuration.function_metrics import *


def filter_kwargs_for_callable(kwargs, callable_object):
    """
    Filters kwargs to include only those that are valid parameters for the callable_object.
    """
    # Get the names of valid parameters for callable_object
    valid_params = set(inspect.getfullargspec(callable_object).args)
    # Create a new dictionary with only the valid parameters
    filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_params}
    return filtered_kwargs


def print_kwargs(kw):
    """Returns a printable version of a kwargs dict"""
    results = {}
    for key, value in kw.items():
        try:
            results[str(key)] = str(value)
        except AttributeError as e:
            print(f"Error printing {key}: {e}")
    return str(results)


class BaseMetric(evals.Eval):
    """Base class for metric evaluations

    Sub-classes are called to run functions on all or parts of conversations.

    Based loosely on:
    https://github.com/openai/evals/blob/main/evals/elsuite/basic/match.py

    """

    def __init__(
        self,
        samples_jsonl: str,
        function_metric_name: str,
        *args,
        **kwargs,  # passed to completion function?
    ):
        self.kwargs = kwargs
        super().__init__(**filter_kwargs_for_callable(kwargs, evals.Eval.__init__))
        self.samples_jsonl = samples_jsonl
        self.function_metric_name = function_metric_name

    def run(self, recorder):
        """
        Called by the `oaieval` CLI to run the eval. The `eval_all_samples` method calls `eval_sample`.

        This overloads the run() method and skips aggregations, since those can be done post-hoc in SQL.
        """
        # Loads data from file
        self.samples = evals.get_jsonl(self.samples_jsonl)

        # Calls 'eval_sample'
        self.eval_all_samples(recorder, self.samples)

        # Evals expects a dict to iterate over
        return {}


class TurnMetric(BaseMetric):

    def eval_sample(self, test_sample, rng: random.Random):
        """
        Called by the `eval_all_samples` method to evaluate a single sample.

        ARGS
        ====
        `test_sample`: a line from the JSONL test file formatted like:
            {'input':[{'role':X1, 'content': Y1}, {'role':X2, 'content': Y2}, ...]}

        This function logs metrics in two ways. First, it computes metrics turn-by-turn.

        Then, it concatenates all the text from each role together, and returns the metric over the concatenated value.
        For this, it codes the 'turn' as -1.

        """
        for turn_ix, turn in enumerate(test_sample["input"]):
            if turn["role"] not in ["system"]:
                # Check if the function name exists in the global namespace and call it
                if self.function_metric_name in globals() and callable(
                    globals()[self.function_metric_name]
                ):
                    if turn.get("content", None) is None:
                        print(turn)
                    metric_value = globals()[self.function_metric_name](turn["content"])
                else:
                    print(
                        "No callable function named "
                        + self.function_metric_name
                        + " found."
                    )
                    metric_value = None
                    # return self.function_metric_name, None

                evals.record.record_metrics(
                    **{
                        "role": turn["role"],
                        "turn": turn_ix,
                        "function_metric_name": self.function_metric_name,
                        "metric_value": metric_value,
                        "content": turn["content"],
                    }
                )


class CompletionMetric(BaseMetric):

    def eval_sample(self, test_sample, rng: random.Random):
        """
        Called by the `eval_all_samples` method to evaluate a single sample.

        ARGS
        ====
        `test_sample`: a line from the JSONL test file formatted like:
            {'input':[{'role':X1, 'content': Y1}, {'role':X2, 'content': Y2}, ...]}

        This function logs metrics in two ways. First, it computes metrics turn-by-turn.

        Then, it concatenates all the text from each role together, and returns the metric over the concatenated value.
        For this, it codes the 'turn' as -1.

        """
        result = self.completion_fn(prompt=test_sample)
        results = result.get_completions()

        # Calculate the metric based on the completion
        for result in results:
            if self.function_metric_name in globals() and callable(
                globals()[self.function_metric_name]
            ):
                if result is None:
                    # TODO log WARNING
                    pass
                metric_value = globals()[self.function_metric_name](result)
            else:
                print("globals", globals())
                raise Exception(
                    "No callable function named "
                    + self.function_metric_name
                    + " found."
                )

                metric_value = None

            # single values get recorded as-is
            if isinstance(metric_value, int) or isinstance(metric_value, float):
                evals.record.record_metrics(
                    **{
                        "role": "assistant",
                        "turn": -1,
                        "function_metric_name": self.function_metric_name,
                        "metric_value": metric_value,
                        "content": result,
                    }
                )
            # dictionaries get recorded separately for each key
            elif isinstance(metric_value, dict):
                for k, v in metric_value.items():
                    print(k, v)
                    evals.record.record_metrics(
                        **{
                            "role": "assistant",
                            "turn": -1,
                            "function_metric_name": f"{self.function_metric_name}_{k}",
                            "metric_value": v,
                            "content": result,
                        }
                    )
            else:
                raise Exception(
                    f"Not sure what to do with metric output! Make sure it is a float/int/dict. Output is: {metric_value}"
                )


class ConversationMetric(BaseMetric):
    """This computes metrics over entire conversations, aggregated by role
    For example, this can be used to answer "how many assistant completions are in this conversation"
    """

    def eval_sample(self, test_sample, rng: random.Random):
        """
        Called by the `eval_all_samples` method to evaluate a single sample.

        ARGS
        ====
        `test_sample`: a line from the JSONL test file formatted like:
            {'input':[{'role':X1, 'content': Y1}, {'role':X2, 'content': Y2}, ...]}

        This function logs metrics by computing a function on each CONVERSATION
        The function will return a JSON like this for each role:
        {
            "role": role,
            "function_metric_name": name,
            "metric_value": value
        }

        """

        # Check if the function name exists in the global namespace and call it
        if self.function_metric_name in globals() and callable(
            globals()[self.function_metric_name]
        ):
            if test_sample is None:
                # TODO log WARNING
                pass
            metric_values = globals()[self.function_metric_name](test_sample["input"])
        else:
            print("No callable function named " + self.function_metric_name + " found.")
            metric_values = None

        # if metric_values is an int or float
        if isinstance(metric_values, int) or isinstance(metric_values, float):
            evals.record.record_metrics(
                **{
                    "function_metric_name": self.function_metric_name,
                    "metric_value": metric_values,
                }
            )
        elif isinstance(metric_values, dict):
            for role, metric_value in metric_values.items():
                evals.record.record_metrics(
                    **{
                        "role": role,
                        "function_metric_name": self.function_metric_name,
                        "metric_value": metric_value,
                    }
                )
        elif isinstance(metric_values, list):
            for entry in metric_values:
                evals.record.record_metrics(
                    **{
                        "role": entry.get("role", None),
                        "function_metric_name": self.function_metric_name,
                        "metric_value": entry.get("value", None),
                    }
                )
