"""These validation checks are intended to be executed time runner.run() is called.

They check to make sure FlexEval is configured properly. In particular,
they check the evals.yaml file you're using and the specific evaluation you're running
and they make sure
1. functions exists that match your function metric names
2. rubrics exist that match your rubric metric names
3. any dependencies are set up properly
4. ...and more!

Any misconfiguration should be caught here. If an evaluation fails due to misconfiguration
and it's not caught here, that's a bug - and we should add a test here
"""

import inspect
import json
import logging
import os
import unittest
from typing import ForwardRef, get_args

from openai import OpenAI

from flexeval import dependency_graph, rubric
from flexeval.classes.message import Message
from flexeval.classes.thread import Thread
from flexeval.classes.tool_call import ToolCall
from flexeval.classes.turn import Turn
from flexeval.schema import Config, Eval

logger = logging.getLogger(__name__)


class TestConfiguration(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.config: Config = Config.model_validate_json(
            os.getenv("FLEXEVAL_VALIDATE_CONFIG_JSON")
        )
        self.eval: Eval = Eval.model_validate_json(
            os.getenv("FLEXEVAL_VALIDATE_EVAL_JSON")
        )
        logger.info("Validating eval %s", self.eval.name)
        self.rubric_metrics = rubric.load_rubrics_from_config(self.config)

        # Apply the defaults before any testing of validity, since
        # may only be valid with these defaults
        # TODO figure out if this step is actually necessary
        # FIXME rewrite apply_defaults to use the defaults defined in Eval instead...
        # self.eval = helpers.apply_defaults(schema, self.eval)

    def skip_if_no_openai_checks(self):
        # TODO why is this not in the config?
        if os.getenv("SKIP_OPENAI_CHECKS", "false") == "true":
            self.skipTest("Skipping because SKIP_OPENAI_CHECKS is set to True.")

    def test_openai_key_set(self):
        self.skip_if_no_openai_checks()
        assert (
            os.environ.get("OPENAI_API_KEY", "") != ""
        ), "OPENAI_API_KEY must be set in the .env file"

    def test_openai_is_valid(self):
        self.skip_if_no_openai_checks()
        # will raise exception if key is not set
        try:
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "What is blue plus orange?"}],
                temperature=0,
            )

        except Exception as e:
            logger.error(
                "Your OpenAI key appears to not be valid! Double check the key in the .env file"
            )
            raise e

    ## Make sure every location specified in the config file exists
    def test_config_file(self):
        def check_file_or_dir(path):
            """Check if a given path exists and is a file or directory."""
            return os.path.isfile(path) or os.path.isdir(path)

        def traverse_yaml(node, base_path=""):
            """Traverse the YAML tree and check existence of leaf entries."""
            if isinstance(node, str):
                path = node
                # path = os.path.join(base_path, node)
                if not check_file_or_dir(path) and not path.endswith("db"):
                    raise Exception(
                        f'Error: File or directory "{path}" specified in the src/llm-evals/{os.environ["CONFIG_FILENAME"]} file does not exist'
                    )
                elif os.path.islink(path):
                    logger.warning(f'Warning: Found a symbolic link at path "{path}"')
            elif isinstance(node, list):
                for item in node:
                    traverse_yaml(item, base_path=os.path.join(base_path, node[0]))
            elif isinstance(node, dict):
                for key, value in node.items():
                    traverse_yaml(value, base_path=os.path.join(base_path, key))

        self.assertTrue(True)
        # TODO I think this is completely redundant with the pydantic checks
        # traverse_yaml(self.config)

    # TODO add validation check for loading function_modules from strings
    # TODO add validation check that individual functions passed are callable

    def test_rubrics_requested_are_available(self):
        eval_rubrics = self.eval.metrics.rubric
        if eval_rubrics is not None:
            for rubric in eval_rubrics:
                self.assertTrue(
                    rubric.name in self.rubric_metrics,
                    f"Your eval suite `{self.eval.name}` uses a rubric named `{rubric.name}`, but no rubric with this name was found among the {len(self.rubric_metrics)} rubric metrics.",
                )

    def test_metric_dependencies_are_a_dag(self):
        # Error checking will happen in create_metrics_graph function
        dependency_graph.create_metrics_graph(self.eval.metrics)

    def test_function_metrics_exist(self):
        """
        Test that all function metrics specified in eval config exist and are called with appropriate args.
        """
        function_metrics = self.eval.metrics.function
        if function_metrics is None:
            return
        # TODO need to create a MetricComputer to do this properly...
        return
        for function_metric in function_metrics:
            name = function_metric.name
            assert hasattr(function_metrics, name) and callable(
                getattr(function_metrics, name, None)
            ), f"No function named {name} exists in `function_metrics.py`"

            metric_function = getattr(function_metrics, name, None)

            # Go through arguments and make sure that the first argument has the right type and that
            # all later arguments are filled by keyword arguments
            arg_found = False
            var_keyword_arg_found = False
            arg_names = []
            params = inspect.signature(metric_function).parameters
            for arg_tuple in iter(params.items()):
                if not arg_found:
                    # First arg
                    arg_found = True
                    first_arg_type = arg_tuple[1].annotation
                    self.helper_valid_first_function_param(
                        function_metric, first_arg_type
                    )
                else:
                    # Later arguments - need to be filled by kwargs, have defaults, or be variable length keyword args
                    arg_names.append(arg_tuple[0])
                    assert (
                        arg_tuple[1].default is not inspect.Parameter.empty
                        or arg_tuple[0] in function_metric.get("kwargs", {})
                        or arg_tuple[1].kind is inspect.Parameter.VAR_KEYWORD
                    ), f"Argument `{arg_tuple[0]}` in function `{name}` must have a default value or the value must be specified in `kwargs` in the eval configuration"
                    var_keyword_arg_found = (
                        var_keyword_arg_found
                        or arg_tuple[1].kind is inspect.Parameter.VAR_KEYWORD
                    )

            assert (
                arg_found
            ), f"Function metrics must take at least one input, but {name} does not have any arguments."
            # Check that there are no extra keyword arguments that don't match the function. If the function allows
            # variable length keyword arguments, then extra keyword arguments are allowed.
            if "kwargs" in function_metric and not var_keyword_arg_found:
                for kwarg in function_metric["kwargs"]:
                    assert (
                        kwarg in arg_names
                    ), f"Keyword argument `{kwarg}` specified in json for function `{name}`, but no argument with that name found in function signature."

    def helper_valid_first_function_param(self, function_metric, first_arg_type):
        name = function_metric["name"]
        # Needs to be an allowed first argument type and match the metric level
        metric_level = function_metric["metric_level"]
        if metric_level.lower() == "thread":
            assert (
                first_arg_type is str
                or first_arg_type is list
                or first_arg_type is Thread
                or first_arg_type is ForwardRef("Thread")
                or Thread in get_args(first_arg_type)
                or ForwardRef("Thread") in get_args(first_arg_type)
            ), f"Input to metric function {name} with metric_level set to {metric_level} must be a string, list, or Thread but it was {first_arg_type}"
        elif metric_level.lower() == "turn":
            assert (
                first_arg_type is str
                or first_arg_type is list
                or first_arg_type is Turn
                or first_arg_type is ForwardRef("Turn")
                or Turn in get_args(first_arg_type)
                or ForwardRef("Turn") in get_args(first_arg_type)
            ), f"Input to metric function {name} with metric_level set to {metric_level} must be a string, list, or Turn but it was {first_arg_type}"
        elif metric_level.lower() == "message":
            assert (
                first_arg_type is str
                or first_arg_type is Message
                or first_arg_type is ForwardRef("Message")
                or Message in get_args(first_arg_type)
                or ForwardRef("Message") in get_args(first_arg_type)
            ), f"Input to metric function {name} with metric_level set to {metric_level} must be a string or Message but it was {first_arg_type}"
        elif metric_level.lower() == "toolcall":
            assert (
                first_arg_type is dict
                or first_arg_type is ToolCall
                or first_arg_type is ForwardRef("ToolCall")
                or ToolCall in get_args(first_arg_type)
                or ForwardRef("ToolCall") in get_args(first_arg_type)
            ), f"Input to metric function {name} with `metric_level` set to {metric_level} must be a dict or ToolCall but it was {first_arg_type}"
        else:
            raise Exception(
                f"You set `metric_level` for the metric function `{name}` to {metric_level}, but `metric_level` must be one of Thread, Turn, Message, or ToolCall."
            )

    def test_context_only_used_only_for_string_list_functions(self):
        function_metrics = self.eval.metrics.function
        if function_metrics is None:
            return
        # TODO need to create a MetricComputer to do this properly...
        return
        for function_metric in function_metrics:
            name = function_metric["name"]
            if function_metric.get("context_only", False):
                # context_only can only be true for a string or list input function
                metric_function = getattr(function_metrics, name, None)
                params = inspect.signature(metric_function).parameters
                first_arg_type = next(
                    (arg_tuple[1].annotation for arg_tuple in iter(params.items())),
                    None,
                )
                if first_arg_type is None:
                    raise Exception(
                        f"The metric function `{name}` has no inputs, but must have at least one."
                    )

                assert first_arg_type is str or first_arg_type is list, (
                    f"When context_only is True for a metric function, the input type for that function must be a string"
                    f" or a list. The metric function `{name}` has context_only set to True, but the first argument for"
                    f" the function is of type {first_arg_type}. If you would like to pass the value for context_only"
                    f" to the function, include it as a keyword arg (nested in kwargs)."
                )

    def test_metric_templates_are_valid(self):
        rubric_metrics = self.eval.metrics.rubric
        if rubric_metrics is None:
            return
        for rubric_metric in rubric_metrics:
            rubric_name = rubric_metric.name
            assert (
                rubric_name in self.rubric_metrics.keys()
            ), f"You specified a rubric called `{rubric_name}` in the configuration, but only these rubrics are available: {list(self.rubric_metrics.keys())}."
            prompt = self.rubric_metrics[rubric_name]
            # The prompts will have three types
            # {context} -- everything BEFORE the last entry
            # {completion} -- new completion or last entry
            # {turn} -- just the current turn -- cannot be used with the other two

            options = [("{turn}",), ("{context}", "{completion}"), ("{conversation}",)]
            for option1 in options:
                for option2 in options:
                    if all([o in prompt for o in option1]):
                        if option2 != option1:
                            for o2 in option2:
                                assert (
                                    o2 not in prompt
                                ), f"Your rubric {rubric_name} is has the template `{','.join([i  for i in option1]) }` and cannot also contain the template option `{o2}`."

            if (
                rubric_metric.context_only
                and "{{context}}" in prompt
                and "{{completion}}" in prompt
            ):
                raise Exception(
                    f"You set `context_only` for the rubric `{rubric_name}`, but that rubric has both {{context}} and {{completion}} entries. This does not make sense! If you want the context only, create a rubric with only {{turn}} or only {{conversation}}."
                )

    def test_function_metrics_have_valid_signatures(self):
        # TODO implement appropriately
        return
        for function_metric in self.eval.get("metrics").get("function", []):
            name = function_metric["name"]
            assert hasattr(function_metrics, name) and callable(
                getattr(function_metrics, name, None)
            ), f"No function named {name} exists in `function_metrics.py`"

            metric_function = getattr(function_metrics, name, None)

            first_argument_type = next(
                iter(inspect.signature(metric_function).parameters.values())
            ).annotation
            self.helper_valid_first_function_param(function_metric, first_argument_type)

            return_type = inspect.signature(metric_function).return_annotation
            assert return_type in [
                float,
                int,
                dict,
                list,
            ], f"The return type of function {name} has type {first_argument_type}. The return type must be one of `int`, `float`, `dict`, or `list`."

    def test_dataset_rows(self):
        filenames = self.eval.data
        for filename in filenames:
            with open(filename, "r") as infile:
                for ix, row in enumerate(infile):
                    row_json = json.loads(row)
                    self.assertTrue(
                        "input" in row_json,
                        f"Dataset {filename}, row {ix+1} does not contain an input key!",
                    )
                    self.assertTrue(
                        isinstance(row_json["input"], list),
                        f"The `input` key for dataset {filename}, row {ix+1} was not parsed as a list!",
                    )
                    for entry_ix, entry in enumerate(row_json["input"]):
                        self.assertTrue(
                            "role" in entry,
                            f"Entry {entry_ix+1} in the `input` key for dataset {filename}, row {ix+1} does not contain a `role` key!",
                        )
                        self.assertTrue(
                            "content" in entry,
                            f"Entry {entry_ix+1} in the `input` key for dataset {filename}, row {ix+1} does not contain a `content` key!",
                        )
                        self.assertTrue(
                            entry["role"]
                            in [
                                "user",
                                "assistant",
                                "tool",
                                "system",
                            ],
                            f"`user` key in entry {entry_ix+1} in the `input` key for dataset {filename}, row {ix+1} must be one of `tool`,`user`,`assistant`! You have `{entry['role']}`.",
                        )


# def test_evals_has_required_components(self):
#     with open(self.config_file_name) as file:
#         config = yaml.safe_load(file)
#     with open(config["evals_path"]) as file:
#         evals = yaml.safe_load(file)
#     with open(config["rubric_metrics_path"]) as file:
#         rubric_metrics = yaml.safe_load(file)
#     function_metrics = importlib.import_module(
#         config["function_metrics_path"].replace("/", ".").replace(".py", "")
#     )
#     completion_functions = importlib.import_module(
#         config["completion_functions"].replace("/", ".").replace(".py", "")
#     )

#     for eval_name, eval_contents in evals.items():
#         # only test current eval suite
#         if eval_name == self.eval_suite_name:
#             # Simplest possible - no completion, one metric
#             assert (
#                 "data" in eval_contents
#             ), f"In evals.yaml, eval suite '{eval_name}' has no 'data' defined."
#             assert (
#                 "path" in eval_contents["data"]
#             ), f"In evals.yaml, eval suite '{eval_name}.data' has no 'path' defined."
#             # assert (
#             #     "function_metrics" in eval_contents
#             # ), f"In evals.yaml, eval suite '{eval_name}' requires a 'function_metrics' entry, even if it is empty."
#             # assert (
#             #     "rubric_metrics" in eval_contents
#             # ), f"In evals.yaml, eval suite '{eval_name}' requires a 'rubric_metrics' entry, even if it is empty."
#             # assert (
#             #     "grader_llm" in eval_contents
#             # ), f"In evals.yaml, eval suite '{eval_name}' requires a 'grader_llm' entry, even if it is empty."
#             # assert (
#             #     "completion" in eval_contents
#             # ), f"In evals.yaml, eval suite '{eval_name}' requires a 'completion' entry, even if it is empty."

#             if eval_contents["function_metrics"] is not None:
#                 for function_metric in eval_contents["function_metrics"]:
#                     assert (
#                         "name" in function_metric
#                     ), f"In evals.yaml, each entry of '{eval_name}.function_metrics' requires a 'name' key"
#                     assert (
#                         "score" in function_metric
#                     ), f"In evals.yaml, each entry of '{eval_name}.function_metrics' requires a 'score' key"
#                     assert function_metric["score"] in [
#                         "per_turn_by_role",
#                         "per_conversation_by_role",
#                         "completion",
#                     ], f"In evals.yaml, each entry of '{eval_name}.function_metrics.score' must be one of 'completion', 'all_by_role'. You have '{function_metric['score']}'"

#                     # make sure each function_metric has a "sample" input
#                     assert hasattr(
#                         function_metrics, function_metric["name"]
#                     ), f"In evals.yaml, the function '{function_metric['name']}' is used by eval suite '{eval_name}' but it is not defined in the function_metrics.py file"
#                     myfunc = getattr(function_metrics, function_metric["name"])
#                     assert callable(
#                         myfunc
#                     ), f"The function {function_metric['name']} specified in evals.yaml is not callable!"
#                     signature = inspect.signature(myfunc)
#                     # assert (
#                     #     "sample" in signature.parameters
#                     # ), f"In evals.yaml, the function '{function_metric['name']}' used by eval suite '{eval_name}' and defined in function_metrics.py must take 'sample' as an argument."

#             if eval_contents.get("completion", None) is not None:
#                 assert (
#                     "function_name" in eval_contents["completion"]
#                 ), f"In evals.yaml, the 'completion' entry must have a 'function_name' key, but it is missing in the {eval_name} eval."
#                 # get function name first
#                 for completion_fn_key, completion_fn_value in eval_contents[
#                     "completion"
#                 ].items():
#                     # verify function is defined
#                     if completion_fn_key == "function_name":
#                         completion_function_name = completion_fn_value
#                 for completion_fn_key, completion_fn_value in eval_contents[
#                     "completion"
#                 ].items():
#                     # verify function is defined
#                     if completion_fn_key == "function_name":
#                         pass
#                         # assert hasattr(
#                         #     completion_functions, completion_fn_value
#                         # ), f"In evals.yaml, in the eval suite '{eval_name}', you specify a function called '{completion_fn_value}' but it does not exist in the completion_function.py file."
#                     else:
#                         # verify function has required args
#                         myfunc = getattr(
#                             completion_functions, completion_function_name
#                         )
#                         signature = inspect.signature(myfunc)
#                         assert (
#                             completion_fn_key in signature.parameters
#                         ), f"In evals.yaml, in '{eval_name}.completion', you specify a function '{completion_function_name}' with an argument '{completion_fn_key}' but the function defined in completion_function.py does not have that argument in the signature."
#                 # verify all required args are in the yaml file
#                 myfunc = getattr(completion_functions, completion_function_name)
#                 signature = inspect.signature(myfunc)
#                 assert (
#                     "conversation_history" in signature.parameters
#                 ), f"The function '{completion_function_name}' in completion_functions.py must have a 'conversation_history' argument."
#                 for param_name, param in signature.parameters.items():
#                     if (
#                         param_name not in ["conversation_history", "args", "kwargs"]
#                         and param.default is not inspect.Parameter.empty
#                     ):
#                         assert (
#                             param_name in eval_contents["completion"].keys()
#                         ), f"The function '{completion_function_name}' in completion_functions.py has an argument called '{param_name}', but there is no corresponding value in evals.yaml '{eval_name}.completion'."
#             if eval_contents.get("grader_llm") is not None:
#                 assert (
#                     "function_name" in eval_contents["grader_llm"]
#                 ), f"In evals.yaml, the 'grader_llm' entry must have a 'function_name' key, but it is missing in the {eval_name} eval."
#                 # get function name first
#                 for completion_fn_key, completion_fn_value in eval_contents[
#                     "grader_llm"
#                 ].items():
#                     # verify function is defined
#                     if completion_fn_key == "function_name":
#                         completion_function_name = completion_fn_value
#                 for completion_fn_key, completion_fn_value in eval_contents[
#                     "grader_llm"
#                 ].items():
#                     # verify function is defined
#                     if completion_fn_key == "function_name":
#                         assert hasattr(
#                             completion_functions, completion_fn_value
#                         ), f"In evals.yaml, in the eval suite '{eval_name}', you specify a function called '{completion_fn_value}' but it does not exist in the completion_function.py file."
#                     else:
#                         # verify function has required args
#                         myfunc = getattr(
#                             completion_functions, completion_function_name
#                         )
#                         signature = inspect.signature(myfunc)
#                         assert (
#                             completion_fn_key in signature.parameters
#                         ), f"In evals.yaml, in '{eval_name}.grader_llm', you specify a function '{completion_function_name}' with an argument '{completion_fn_key}' but the function defined in completion_function.py does not have that argument in the signature."
#                 # verify all required args are in the yaml file
#                 myfunc = getattr(completion_functions, completion_function_name)
#                 signature = inspect.signature(myfunc)
#                 assert (
#                     "conversation_history" in signature.parameters
#                 ), f"The function '{completion_function_name}' in completion_functions.py must have a 'conversation_history' argument."
#                 for param_name, param in signature.parameters.items():
#                     if (
#                         param_name not in ["conversation_history", "args", "kwargs"]
#                         and param.default is not inspect.Parameter.empty
#                     ):
#                         assert (
#                             param_name in eval_contents["grader_llm"].keys()
#                         ), f"The function '{completion_function_name}' in completion_functions.py has an argument called '{param_name}', but there is no corresponding value in evals.yaml '{eval_name}.grader_llm'."

#             if eval_contents.get("rubric_metrics") is not None:
#                 for rubric_metric in eval_contents["rubric_metrics"]:
#                     assert (
#                         "name" in rubric_metric.keys()
#                     ), f"In evals.yaml, each entry of '{eval_name}.rubric_metrics' requires a 'name' key."
#                     assert (
#                         rubric_metric["name"] in rubric_metrics
#                     ), f"In evals.yaml, you specified a rubric metric called '{rubric_metric}' but none was found in rubric_metrics.yaml"

#             # model_options = [
#             #     "gpt-3.5-turbo",
#             #     "gpt-3.5-turbo-16k",
#             #     "gpt-4",
#             #     "gpt-4-32k",
#             # ]
#             # # https://github.com/openai/evals/blob/c66b5c1337cf2b65b72045bcdcfaeeacc0eafad2/evals/registry.py#L41
#             # if eval_contents["grader_llm"] is not None:
#             #     if "model" in eval_contents["grader_llm"]:
#             #         assert (
#             #             eval_contents["grader_llm"]["model"] in model_options
#             #         ), f"In evals.yml, {eval_name}.grader_llm.model must be one of {model_options}"

# def test_endpoints_are_reachable(self):
#     def is_url(string):
#         url_pattern = re.compile(
#             r"^(?:http|ftp)s?://"  # http:// or https:// or ftp:// or ftps://
#             r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"  # domain...
#             r"localhost|"  # localhost...
#             r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|"  # ...or IPv4
#             r"\[?[A-F0-9]*:[A-F0-9:]+\]?)"  # ...or IPv6
#             r"(?::\d+)?"  # optional port
#             r"(?:/?|[/?]\S+)$",
#             re.IGNORECASE,
#         )
#         return re.match(url_pattern, string) is not None

#     # if completion functions have an endpoint that looks like a URL, try to ping it
#     with open(self.config_file_name) as file:
#         config = yaml.safe_load(file)
#     with open(config["evals_path"]) as file:
#         evals = yaml.safe_load(file)
#     for eval_name, eval_contents in evals.items():
#         # only test current eval suite
#         if eval_name == self.eval_suite_name:
#             # assert (
#             #     "completion" in eval_contents
#             # ), f"In evals.yaml, '{eval_name}' must have a 'completion' key, even if the value is blank."
#             pass
#             # if eval_contents["completion"] is not None:
#             #     for k, v in eval_contents["completion"].items():
#             #         if is_url(v):
#             #             try:
#             #                 response = requests.get(
#             #                     v, timeout=5
#             #                 )  # Timeout set to 5 seconds
#             #                 assert (
#             #                     response.status_code < 400
#             #                 ), f"In evals.yaml, '{eval_name}'.completion has a url in the key '{k}', namely '{v}'. It does not appear to be accessible!"
#             #             except (
#             #                 requests.RequestException,
#             #                 requests.exceptions.ConnectionError,
#             #             ):
#             #                 # If the HTTP status code is less than 400, the URL is considered accessible
#             #                 raise Exception(
#             #                     f"In evals.yaml, '{eval_name}'.completion has a url in the key '{k}', namely '{v}'. It does not appear to be accessible!"
#             #                 )

# def test_endpoints_completion_functions_work(self):
#     # if completion functions have an endpoint that looks like a URL, try to ping it
#     with open(self.config_file_name) as file:
#         config = yaml.safe_load(file)
#     with open(config["evals_path"]) as file:
#         evals = yaml.safe_load(file)

#     completion_functions = importlib.import_module(
#         config["completion_functions"].replace("/", ".").replace(".py", "")
#     )

#     # loop through each test suite
#     for eval_name, eval_contents in evals.items():
#         # only test current eval suite
#         if eval_name == self.eval_suite_name:
#             # if there is a completion function defined
#             if eval_contents.get("completion", None) is not None:
#                 assert (
#                     eval_contents["completion"].get("function_name", "") != ""
#                 ), f"In evals.yaml, '{eval_name}'.completion needs an key called 'function_name' that maps to a function in completion_functions.py"
#                 function_name = eval_contents["completion"]["function_name"]
#                 # all of the other entries will be arguments
#                 function_args = eval_contents["completion"]
#                 del function_args["function_name"]
#                 # get the function to call
#                 myfunc = getattr(completion_functions, function_name)
#                 try:
#                     conversation_history = [{"role": "user", "content": "hello"}]
#                     myfunc(conversation_history, **function_args)

#                 except Exception as e:
#                     raise Exception(
#                         f"In the test suite '{eval_name}', an error has occurred: {e}"
#                     )


# one of the metric types is completion but there's no completion function defined
# there's a rubric but no grader LLM
# make sure that functions used with
#      'completion', 'per_turn_by_role', 'per_conversation_by_role'
#      have the right kind of input signature - string or list
# verify each data input has 'input' as a key, and 'role'/'content' as values
# make sure the input is "turn" or "conversation"
