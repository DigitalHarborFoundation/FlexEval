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
    results = {}
    for key, value in kw.items():
        try:
            results[str(key)] = str(value)
        except AttributeError as e:
            print(f"Error printing {key}: {e}")
    return str(results)


# Based loosely on:
# https://github.com/openai/evals/blob/main/evals/elsuite/basic/match.py
class MetricBase(evals.Eval):
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


class MetricTurnByRole(MetricBase):
    def run(self, recorder):
        """
        Called by the `oaieval` CLI to run the eval. The `eval_all_samples` method calls `eval_sample`.
        """
        # Loads data from file
        self.samples = evals.get_jsonl(self.samples_jsonl)

        # Calls 'eval_sample'
        self.eval_all_samples(recorder, self.samples)
        all_metrics = recorder.get_metrics()

        # Aggregates by role
        # First extract all roles and metric names
        metrics_by_turn = {}
        roles = set([i["role"] for i in all_metrics])
        function_metric_names = set([i["function_metric_name"] for i in all_metrics])

        # Second extract metric values
        for function_metric_name in function_metric_names:
            metrics_by_turn_lists = {}
            for role in roles:
                if role not in metrics_by_turn_lists:
                    metrics_by_turn_lists[role] = []
                for i in all_metrics:
                    if i["role"] == role and i["turn"] >= 0:
                        metrics_by_turn_lists[role].append(i["metric_value"])

        # Third compute average
        outputs = []
        for function_metric_name in function_metric_names:
            metrics_by_turn[function_metric_name] = {}
            for role in roles:
                outputs += [
                    {
                        "metric_name": function_metric_name,
                        "metric_aggregate_value": max(metrics_by_turn_lists[role]),
                        "aggregation": "max",
                        "role": role,
                    },
                    {
                        "metric_name": function_metric_name,
                        "metric_aggregate_value": sum(metrics_by_turn_lists[role])
                        / len(metrics_by_turn_lists[role]),
                        "aggregation": "mean",
                        "role": role,
                    },
                    {
                        "metric_name": function_metric_name,
                        "metric_aggregate_value": min(metrics_by_turn_lists[role]),
                        "aggregation": "min",
                        "role": role,
                    },
                ]

        return {"results": outputs}

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
        concatenated_text = {}
        for turn_ix, turn in enumerate(test_sample["input"]):
            if turn["role"] not in concatenated_text:
                concatenated_text[turn["role"]] = ""
            concatenated_text[turn["role"]] += f'\n{turn["content"]}'

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
                    "turn": turn_ix + 1,
                    "function_metric_name": self.function_metric_name,
                    "metric_value": metric_value,
                }
            )


class MetricCompletionOnly(MetricBase):
    def run(self, recorder):
        """
        Called by the `oaieval` CLI to run the eval. The `eval_all_samples` method calls `eval_sample`.
        """
        self.samples = evals.get_jsonl(self.samples_jsonl)

        # evaluates metrics on data
        self.eval_all_samples(recorder, self.samples)
        all_metrics = recorder.get_metrics()

        # set of evaluated metrics - there should be just one here
        function_metric_names = set([i["function_metric_name"] for i in all_metrics])

        metric_values_by_name = {}
        for function_metric_name in function_metric_names:
            metric_values_by_name[function_metric_name] = []
        for record in all_metrics:
            metric_values_by_name[record["function_metric_name"]].append(
                record["metric_value"]
            )

        outputs = []
        for metric_name, metric_value in metric_values_by_name.items():
            outputs += [
                {
                    "metric_name": metric_name,
                    "metric_aggregate_value": round(
                        sum(metric_value) / len(metric_value), 3
                    ),
                    "aggregation": "mean",
                    "role": "assistant",
                },
                {
                    "metric_name": metric_name,
                    "metric_aggregate_value": max(metric_value),
                    "aggregation": "max",
                    "role": "assistant",
                },
                {
                    "metric_name": metric_name,
                    "metric_aggregate_value": min(metric_value),
                    "aggregation": "min",
                    "role": "assistant",
                },
            ]

        return {"results": outputs}

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
                        }
                    )
            else:
                raise Exception(
                    f"Not sure what to do with metric output! Make sure it is a float/int/dict. Output is: {metric_value}"
                )


class MetricConversationByRole(MetricBase):
    """This computes metrics over entire conversations, aggregated by role
    For example, this can be used to answer "how many assistant completions are in this conversation"
    """

    def run(self, recorder):
        """
        Called by the `oaieval` CLI to run the eval. The `eval_all_samples` method calls `eval_sample`.
        """
        # Loads data from file
        self.samples = evals.get_jsonl(self.samples_jsonl)

        # Calls 'eval_sample' - where sample is a full conversation
        self.eval_all_samples(recorder, self.samples)
        all_metrics = recorder.get_metrics()

        # The metrics are ALREADY by role in the format
        # {
        #  "role": role,
        #  "metric_value": value...
        # }
        # So we just take aggregates over these across all conversations

        # First extract all roles and metric names
        roles = set([i["role"] for i in all_metrics])
        # function_metric_names = set(
        #     [i["function_metric_name"] for i in all_metrics]
        # )  # there will only be ONE of these

        # Second extract values for each role/metric combo
        metrics_by_conversation_list = {}
        for role in roles:
            if role not in metrics_by_conversation_list:
                metrics_by_conversation_list[role] = []
            for i in all_metrics:
                if i["role"] == role:
                    metrics_by_conversation_list[role].append(i["metric_value"])

        # Third compute average
        outputs = []
        for role in roles:
            outputs += [
                {
                    "metric_name": self.function_metric_name,
                    "metric_aggregate_value": max(metrics_by_conversation_list[role]),
                    "aggregation": "max",
                    "role": role,
                },
                {
                    "metric_name": self.function_metric_name,
                    "metric_aggregate_value": sum(metrics_by_conversation_list[role])
                    / len(metrics_by_conversation_list[role]),
                    "aggregation": "mean",
                    "role": role,
                },
                {
                    "metric_name": self.function_metric_name,
                    "metric_aggregate_value": min(metrics_by_conversation_list[role]),
                    "aggregation": "min",
                    "role": role,
                },
            ]

        return {"results": outputs}

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

        for role, metric_value in metric_values.items():
            evals.record.record_metrics(
                **{
                    "role": role,
                    "function_metric_name": self.function_metric_name,
                    "metric_value": metric_value,
                }
            )
