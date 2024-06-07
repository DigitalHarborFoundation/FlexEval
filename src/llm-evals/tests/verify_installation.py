import unittest
import os
from openai import OpenAI
import yaml
import sys
import dotenv
import networkx as nx

dotenv.load_dotenv()


class TestConfiguration(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.eval_suite_name = sys.argv[1]
        self.config_file_name = os.getenv(
            "CONFIG_FILENAME"
        )  # was set before this was called

        with open(self.config_file_name) as file:
            self.config = yaml.safe_load(file)
        with open(self.config["evals_path"]) as file:
            self.user_evals = yaml.safe_load(file)
        with open(self.config["rubric_metrics_path"]) as file:
            self.rubric_metrics = yaml.safe_load(file)

    def test_env_file_exists(self):
        assert os.path.exists(
            ".env"
        ), ".env file must be defined in the root of the project folder"

    def test_openai_key_set(self):
        assert (
            os.environ.get("OPENAI_API_KEY", "") != ""
        ), "OPENAI_API_KEY must be set in the .env file"

    def test_openai_is_valid(self):
        # will raise exception if key is not set
        try:
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "What is blue plus orange?"}],
                temperature=0,
            )

        except Exception as e:
            print(
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
                    print(f'Warning: Found a symbolic link at path "{path}"')
            elif isinstance(node, list):
                for item in node:
                    traverse_yaml(item, base_path=os.path.join(base_path, node[0]))
            elif isinstance(node, dict):
                for key, value in node.items():
                    traverse_yaml(value, base_path=os.path.join(base_path, key))

        traverse_yaml(self.config)

    def test_tests_are_unique(self):
        # this is tricky because the test names ALSO can't overlap with pre-installed eval names......
        import evals

        evals_location = os.path.dirname(evals.__file__)
        evals_test_path = os.path.join(evals_location, "elsuite")
        existing_tests = os.listdir(evals_test_path)
        for user_eval in self.user_evals.keys():
            assert (
                user_eval not in existing_tests
            ), f"Your eval name `{user_eval}` is already in use by OpenAI Evals. Please use a different name."

    def test_rubrics_requested_are_available(self):
        if (
            self.user_evals[self.eval_suite_name].get("rubric_metrics", None)
            is not None
        ):
            for rubric in self.user_evals[self.eval_suite_name].get("rubric_metrics"):
                assert (
                    "name" in rubric
                ), f"All rubric_metrics entries must have an entry with a `name` key."
                assert (
                    rubric["name"] in self.rubric_metrics.keys()
                ), f"Your eval suite `{self.eval_suite_name}` uses a rubric named `{rubric['name']}`, but no rubric with this name was found in configuration/rubric_metrics.yaml."

    def test_datafiles_are_found(self):
        data_paths = self.user_evals[self.eval_suite_name].get("data", {})
        for data_path in data_paths:
            assert os.path.exists(
                data_path
            ), f"The data file you specified is not found. You asked for `{data_path}`, which has the absolute path `{os.path.abspath(data_path)}"

    def test_metric_dependencies_are_a_dag(self):

        user_metrics = self.user_evals[self.eval_suite_name].get("metrics", [])
        # Create a directed graph
        # I think I switched around 'child' and 'parent' here but it doesn't matter for this purpose
        G = nx.DiGraph()
        for metric_type in ["function", "rubric"]:
            if metric_type in user_metrics:
                assert isinstance(
                    user_metrics.get(metric_type, {}), list
                ), f"Metrics of type {metric_type} must be a list"

                for metric_dict in user_metrics.get(metric_type):
                    assert isinstance(
                        metric_dict, dict
                    ), f"Metric must be defined as a dict. You provided: {metric_dict}"
                    assert (
                        "name" in metric_dict
                    ), f"Metric must be have a `name` key. You provided: {metric_dict}"

                    # if the metric depends on something, that is the PARENT
                    child_metric = metric_dict.get("name")
                    # print("Adding edge from", "root", child_metric)
                    if "depends_on" in metric_dict:
                        assert isinstance(
                            metric_dict.get("depends_on"), list
                        ), f"Entries of `depends_on` requirements for the metric {metric_dict.get('name','')} must be formatted as a list, even if it has just one entry."
                        for requirement in metric_dict.get("depends_on", []):
                            assert (
                                "min_value" in requirement or "max_value" in requirement
                            ), f"Metric requirement must be have either `min_value`, `max_value`, or both. You provided: {requirement}."
                            assert (
                                "name" in requirement
                            ), f"Metric must be have a `name` key. You provided: {metric_dict}"
                            parent_metric = requirement.get("name")
                            # Add nodes and edges
                            G.add_edge(child_metric, parent_metric)
                    else:
                        G.add_edge(child_metric, "root")

        # Print all nodes
        self.metric_graph = G
        self.metric_graph_text = "Metric Dependencies:"
        for edge in G.edges():
            self.metric_graph_text += (
                f"\n{'' if edge[1] == 'root' else edge[1]} -> {edge[0]}"
            )

        assert nx.is_directed_acyclic_graph(
            self.metric_graph
        ), "The set of metric dependencies must be acyclic! You have cyclical dependencies."


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