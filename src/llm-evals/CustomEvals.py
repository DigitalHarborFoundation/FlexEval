import random
import inspect
import evals
import evals.metrics
import evals.record
from evals.elsuite.modelgraded.classify import ModelBasedClassify
from configuration.function_metrics import *
from collections import Counter
from random import Random

import evals
import evals.record
from evals.elsuite.modelgraded.classify_utils import (
    classify,
    sample_and_concat_n_completions,
)
from evals.elsuite.utils import PromptFn, scrub_formatting_from_prompt


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
        Called by the `eval_all_samples` method to evaluate a single sample
        where a sample is a conversation from the dataset, one line of the jsonl.

        ARGS
        ====
        `test_sample`: a line from the JSONL test file formatted like:
            {'input':[{'role':X1, 'content': Y1}, {'role':X2, 'content': Y2}, ...]}


        """
        print("in eval sample")
        for turn_ix, turn in enumerate(test_sample["input"]):
            if turn["role"] not in ["system"]:
                # Check if the function name exists in the global namespace and call it
                if self.function_metric_name in globals() and callable(
                    globals()[self.function_metric_name]
                ):
                    if turn.get("content", None) is None:
                        print(turn)

                    metric_value = globals()[self.function_metric_name](turn["content"], **self.kwargs)
                else:
                    print(
                        "No callable function named "
                        + self.function_metric_name
                        + " found."
                    )
                    metric_value = None
                    # return self.function_metric_name, None

                try:
                    if isinstance(metric_value, int) or isinstance(metric_value, float):
                        evals.record.record_metrics(
                            **{
                                "role": turn["role"],
                                "turn": turn_ix,
                                "function_metric_name": self.function_metric_name,
                                "metric_value": metric_value,
                                "content": turn["content"],
                            }
                        )
                    elif isinstance(metric_value, dict):
                        for k, v in metric_value.items():
                            evals.record.record_metrics(
                                **{
                                    "role": turn["role"],
                                    "turn": turn_ix,
                                    "function_metric_name": f"{self.function_metric_name}_{k}",
                                    "metric_value": v,
                                    "content": turn["content"],
                                }
                            )
                    else:
                        raise Exception(
                            f"Not sure what to do with metric output from {self.function_metric_name}! Make sure it is a float/int/dict. Output is: {metric_value}"
                        )
                except:
                    raise Exception(
                        f"Not sure what to do with metric output from function {self.function_metric_name}! Double-check that it is one of the supported types."
                    )


class CompletionMetric(BaseMetric):

    def eval_sample(self, test_sample, rng: random.Random):
        """
        Called by the `eval_all_samples` method to evaluate a single sample
        where a sample is a conversation from the dataset, one line of the jsonl.

        ARGS
        ====
        `test_sample`: a line from the JSONL test file formatted like:
            {'input':[{'role':X1, 'content': Y1}, {'role':X2, 'content': Y2}, ...]}

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

                metric_value = globals()[self.function_metric_name](result, **self.kwargs)
            else:
                print("globals", globals())
                raise Exception(
                    "No callable function named "
                    + self.function_metric_name
                    + " found."
                )

                metric_value = None

            # single values get recorded as-is
            try:
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
                        f"Not sure what to do with metric output from function {self.function_metric_name}! Make sure it is a float/int/dict. Output is: {metric_value}"
                    )
            except:
                raise Exception(
                    f"Not sure what to do with metric output from function {self.function_metric_name}! Double-check that it is one of the supported types."
                )


class ConversationMetric(BaseMetric):
    """This computes metrics over entire conversations, aggregated by role
    For example, this can be used to answer "how many assistant completions are in this conversation"
    """

    def eval_sample(self, test_sample, rng: random.Random):
        """
        Called by the `eval_all_samples` method to evaluate a single sample
        where a sample is a conversation from the dataset, one line of the jsonl.

        ARGS
        ====
        `test_sample`: a line from the JSONL test file formatted like:
            {'input':[{'role':X1, 'content': Y1}, {'role':X2, 'content': Y2}, ...]}

        This function logs metrics by computing a function on each CONVERSATION
        The function will record a JSON like this for each role:
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
 
            metric_values = globals()[self.function_metric_name](test_sample["input"], **self.kwargs)
        else:
            print("No callable function named " + self.function_metric_name + " found.")
            metric_values = None

        # if metric_values is an int or float
        try:
            if isinstance(metric_values, int) or isinstance(metric_values, float):
                evals.record.record_metrics(
                    **{
                        "function_metric_name": self.function_metric_name,
                        "metric_value": metric_values,
                    }
                )
            elif isinstance(metric_values, dict):
                for k, v in metric_values.items():
                    evals.record.record_metrics(
                        **{
                            "function_metric_name": f"{self.function_metric_name}_{k}",
                            "metric_value": v,
                        }
                    )
            elif isinstance(metric_values, list):
                for entry in metric_values:
                    evals.record.record_metrics(
                        **{
                            "role": entry.get("role", None),
                            "function_metric_name": f"{self.function_metric_name}_{entry.get('metric', '')}",
                            "metric_value": entry.get("value", None),
                        }
                    )
            else:
                raise Exception(
                    f"Not sure what to do with metric output from function {self.function_metric_name}! Double-check that it is one of the supported types."
                )
        except:
            raise Exception(
                f"Not sure what to do with metric output from function {self.function_metric_name}! Double-check that it is one of the supported types."
            )


class RubricMetric(ModelBasedClassify):

    def eval_sample(self, test_sample: dict, rng: Random) -> None:
        """Evaluate a single sample.

        Recorded metrics are always: one of the self.choice_strings, or "__invalid__".
        """
        # process test_sample
        for k in self.mg.input_outputs:
            test_sample[k] = scrub_formatting_from_prompt(test_sample[k])

        # run policy completions
        completions = {}
        for k, v in self.mg.input_outputs.items():
            if v in test_sample:  # test_sample already has completion, skip.
                continue
            if self.multicomp_n > 1:
                completion = sample_and_concat_n_completions(
                    self.completion_fns,
                    prompt=test_sample[k],
                    template_i=self.mg.output_template,
                    sample_kwargs=self.sample_kwargs,
                    n=self.multicomp_n,
                )
            else:
                get_input_completion = PromptFn(
                    test_sample[k],
                    completion_fn=self.completion_fn,
                    **self.sample_kwargs,
                )
                completion, _ = get_input_completion()
            completions[v] = completion

        # run modelgraded eval
        metrics = {}
        choice, info = classify(
            mg=self.mg,
            completion_fn=self.eval_completion_fn,
            completion_kwargs=self.eval_kwargs,
            eval_type=self.eval_type,
            n=self.multicomp_n,
            match_fn=self.match_fn,
            format_kwargs={**completions, **test_sample, **self.modelgraded_spec_args},
        )

        metrics.update(
            dict(
                choice=choice,
                metric_value=info["score"],
                content=completions.get("completion", None),
                turn=-1,
                role="assistant" if completions.get("completion", False) else None,
                # function_metric_name=
            )
        )
        # json_extract(data, '$.function_metric_name') AS function_metric_name,

        # run metaeval if requested
        if self.metaeval:
            assert "choice" in test_sample
            metrics["metascore"] = choice == test_sample["choice"]

        evals.record.record_metrics(**metrics)

        return choice

    def run(self, recorder):
        samples = self.get_samples()

        self.eval_all_samples(recorder, samples)
        record_metrics = {}

        all_sample_metrics = recorder.get_metrics()
        if not all_sample_metrics:
            return record_metrics

        # record the counts
        choices = [m["choice"] for m in all_sample_metrics]
        counts = dict(Counter(choices))
        record_metrics.update({f"counts/{k}": v for k, v in counts.items()})

        # # record the scores
        # scores = [m["score"] for m in all_sample_metrics if m["score"] is not None]
        # if scores:
        #     record_metrics["score"] = sum(scores) / len(scores)
        # metascores = [m["metascore"] for m in all_sample_metrics if "metascore" in m]
        # if metascores:
        #     record_metrics["metascore"] = sum(metascores) / len(metascores)

        # return record_metrics
        return {}
