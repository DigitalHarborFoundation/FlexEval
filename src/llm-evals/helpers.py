import json
import networkx as nx
from typing import List, Dict, Any, Union, AnyStr

import hashlib
import datetime


def generate_hash():
    """Create a random 8-digit id"""
    # Create a new SHA-256 hash object
    hash_object = hashlib.sha256()

    # Update the hash object with the bytes of the string
    hash_object.update(datetime.datetime.now().isoformat().encode())

    # Get the hexadecimal digest of the hash
    full_hash = hash_object.hexdigest()

    # Return the first 8 digits of the hash
    return full_hash[:8]


def create_metrics_graph(user_metrics: dict) -> List[Any]:
    """Input is the metrics dictionary with keys 'function' and 'rubric', each of which maps to a list
    Output is list of string representations of the nodes in the graph, in topological order

    Each entry and dependency will get an ID so they are easy to match later

    TODO - make lots of tests for this

    """

    # Create a directed graph
    G = nx.DiGraph()
    metric_graph_dict = {}

    # make an intermediate datastructure that adds IDs to all listed evaluations
    user_metrics_with_ids = {}
    for evaluation_type in user_metrics.keys():
        user_metrics_with_ids[evaluation_type] = []
        # add a hash to every metric in the list
        for metric_dict in user_metrics[evaluation_type]:
            metric_with_id = {"id": generate_hash()}
            for k, v in metric_dict.items():
                metric_with_id[k] = v
            user_metrics_with_ids[evaluation_type].append(metric_with_id)

    # now that all potential parents have IDs, find parents for each child
    for evaluation_type in user_metrics.keys():
        for metric_dict in user_metrics_with_ids[evaluation_type]:

            parent_metrics, depends_on_with_parent_ids = get_parent_metrics(
                all_metrics=user_metrics_with_ids, child=metric_dict
            )
            metric_dict["depends_on"] = depends_on_with_parent_ids
            # print("\n")
            # print("parent", parent_metrics)
            # print("depends", depends_on_with_parent_ids)

            child_metric_str, evaluation_name = get_metric_info(metric_dict)

            # Now construct the graph
            # Add an edge, which implicitly adds nodes where necessary
            if len(parent_metrics) > 0:
                for parent_metric_dict in parent_metrics:
                    parent_metric_str, _ = get_metric_info(parent_metric_dict)
                    G.add_edge(parent_metric_str, child_metric_str)
                # make 'canonical' representation of child
                metric_graph_dict[child_metric_str] = {
                    "evaluation_name": evaluation_name,  # function or rubric name
                    "evaluation_type": evaluation_type,
                }
                for k, v in metric_dict.items():
                    if k not in [
                        "function_name",
                        "rubric_name",
                        "type",
                        "name",
                    ]:
                        metric_graph_dict[child_metric_str][k] = v

                # # copy over details of parent metric that aren't already present
                # for k, v in parent_metric_dict.items():
                #     if k not in metric_graph_dict[child_metric]:
                #         metric_graph_dict[child_metric][k] = v
            else:
                # if there is no parent, just add a node by itself
                G.add_node(child_metric_str)
                metric_graph_dict[child_metric_str] = {
                    "evaluation_name": evaluation_name,  # function or rubric name
                    "evaluation_type": evaluation_type,
                }
                for k, v in metric_dict.items():
                    if k not in [
                        "function_name",
                        "rubric_name",
                        "type",
                        "name",
                    ]:
                        metric_graph_dict[child_metric_str][k] = v

    # Make string representation with all nodes for error printing in assertion
    graph_string = "Metric Dependencies:"
    for edge in G.edges():
        graph_string += f"\n{'' if edge[1] == 'root' else edge[1]} -> {edge[0]}"
    # print("GRAPH STRING")
    # print(graph_string)
    assert nx.is_directed_acyclic_graph(
        G
    ), "The set of metric dependencies must be acyclic! You have cyclical dependencies. {graph_string}"

    # Set up sequence of evaluations
    # Perform topological sort
    # This is the order in which metrics will be evaluated
    # and the conditions under which they will be evaluated
    topological_order = list(nx.topological_sort(G))
    # print("\n")
    # for n in topological_order:
    #     print(n)
    # print("\n")
    # for k in metric_graph_dict:
    #     print(k)
    metric_graph = [metric_graph_dict[node] for node in topological_order]
    import sys

    # print("FINAL")
    # print(metric_graph)
    # sys.exit()
    return metric_graph


def get_metric_info(single_metric: dict):
    """Input will be a single metric dictionary
    Output will be
    - string representation of metric using json.dumps
    - evaluation_name - function_name or rubric_name
    """
    return json.dumps(single_metric), single_metric.get("name")


def get_parent_metrics(all_metrics: dict, child: dict):
    """metrics_graph_ordered_list will be a list of metrics in order in which they should be run

    This function takes the eval represented by "child" and finds ALL evals in "all_metrics"
    that quality as the child's immediate parent

    An eval can qualify as a parent by having a matching name, type, context_only, last_turn_only
    At this point, we won't have enough information to decide whether the child should be run
    (since the child might have additional requirements on the output of the parent)
    but this is enough to tell us that the child should be run AFTER the parent



    """

    # if we use defaults in "depends_on", we might ends up with non-matches accidentally
    # for a dependency, multiple keys might be listed
    # We should find at least one parent that matches ALL of those key/value pairs, otherwise raise an error
    parents = []
    depends_on_with_id_added = []
    for requirement in child.get("depends_on", []):
        candidate_parents = []
        allowed_types = ["function", "rubric"]
        # if requirement has the type narrowed down, then narrow it down here too
        if "type" in requirement:
            allowed_types = [requirement["type"]]
        for candidate_type in allowed_types:
            for candidate in all_metrics.get(candidate_type, []):
                # assume the candidate is a match unless demonstrated otherwise
                matches = True

                # print("\n")
                # print("requirement", requirement)
                # print("candidate", candidate)

                # if it's not the right type, don't match it
                if "type" in requirement and candidate_type not in allowed_types:
                    matches = False
                    # print("here1")

                # if the level of this metric doesn't match the level
                # of the child, don't match it - we only allow dependencies at the
                # same level of analysis
                if child.get("metric_level") != candidate.get("metric_level"):
                    matches = False

                # if the conditionals are listed in the depends_on entry but don't match...
                conditionals = ["last_turn_only", "context_only", "name", "kwargs"]
                for conditional in conditionals:
                    if conditional in requirement and (
                        requirement.get(conditional, None) != candidate.get(conditional)
                    ):
                        matches = False
                        # print("here2")
                if matches:
                    candidate_parents.append(candidate)
                    # for k, v in candidate.items():
                    #     if k not in requirement and k != "depends_on":
                    #         requirement[k] = v
                    # print("HELP")
                    # print(requirement)
                    # print(candidate)
                    requirement["parent_id"] = candidate["id"]
                    depends_on_with_id_added.append(requirement)
        # print("candidate_parents", candidate_parents)
        assert (
            len(candidate_parents) > 0
        ), f"We were unable to locate any match for the `depends_on` entry `{json.dumps(requirement,indent=4)}` in the metric `{json.dumps(child,indent=4)}`. The full set of parent candidates is `{json.dumps(all_metrics,indent=4)}`."
        assert (
            len(candidate_parents) < 2
        ), f"We located more than one match for the `depends_on` entry `{json.dumps(requirement,indent=4)}` in the metric `{json.dumps(child,indent=4)}`. The matches were `{json.dumps(candidate_parents,indent=4)}`. Please add another criterion to disambiguate."
        parents += candidate_parents

    return parents, depends_on_with_id_added


def apply_defaults(schema, data, path=None):
    # Initialize path as an empty list if None. This will store the navigation path in the schema.
    if path is None:
        path = []

    if data is None:
        # If data is None and defaults are specified, apply them
        return schema.get("default")

    if isinstance(data, dict):
        # Process dictionaries
        if "properties" in schema:
            # Loop over each schema property
            for key, subschema in schema["properties"].items():
                # Update path with current property
                new_path = path + [key]
                if key in data:
                    # Recursively apply defaults, pass the path along
                    data[key] = apply_defaults(subschema, data[key], new_path)
                elif "default" in subschema:
                    # Apply default if the key is not in the data
                    data[key] = subschema["default"]
                    # print("setting", path, key, subschema["default"])
        elif "items" in schema:
            if "properties" in schema["items"]:
                # Loop over each schema property
                for key, subschema in schema["items"]["properties"].items():
                    # Update path with current property
                    new_path = path + [key]
                    if key in data:
                        # Recursively apply defaults, pass the path along
                        data[key] = apply_defaults(subschema, data[key], new_path)
                    elif "default" in subschema:
                        # Apply default if the key is not in the data
                        data[key] = subschema["default"]

        if path == ["metrics", "function"]:
            # for functions, metric_name will be set at runtime
            # # if metric_name isn't already set -- set it to function_name
            # if "metric_name" not in data:
            #     data["metric_name"] = data["name"]
            data["type"] = "function"
        if path == ["metrics", "rubric"]:
            data["type"] = "rubric"
            # for rubrics, there will only ever be one metric per run
            # so we already know the metric_name
            # no - set this later for reasons
            # data["metric_name"] = data["name"]

        return data

    if isinstance(data, list) and "items" in schema:
        # Process lists by applying defaults to each item
        item_schema = schema["items"]
        # Apply defaults to each item in the list, passing along the path
        return [apply_defaults(item_schema, item, path) for item in data]

    return data


# for verify installation
# if function_name is defined, rubric
# make sure "function" and "rubric" default to empty lists
# TODO - don't set defaults in "depends_on" to make matching more flexible
# evaluation_name: my_rubric
# evaluation_type: rubric
# metric_name: <
