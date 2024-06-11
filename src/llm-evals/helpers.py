import json
import networkx as nx
from typing import List, Dict, Any, Union, AnyStr


def create_metrics_graph(metrics_dict: str) -> List[Any]:
    """Input is a json representation of the metrics dictionary.
    Output is
    - list of string representations of the nodes in the graph, in topological order
    """

    user_metrics = json.loads(metrics_dict)
    # Create a directed graph
    G = nx.DiGraph()
    metric_graph_dict = {}
    for evaluation_type in user_metrics.keys():

        for metric_dict in user_metrics[evaluation_type]:

            # if the metric depends on something, that is the PARENT
            child_metric, evaluation_name = get_metric_info(metric_dict)
            # for requirement in metric_dict.get("depends_on", []):
            parent_metrics = get_parent_metrics(
                all_metrics=user_metrics, child=metric_dict
            )

            # Add an edge, which implicitly adds nodes where necessary
            if len(parent_metrics) > 0:
                for parent_metric_dict in parent_metrics:
                    parent_metric_str, _ = get_metric_info(parent_metric_dict)
                    G.add_edge(parent_metric_str, child_metric)
                metric_graph_dict[child_metric] = {
                    "evaluation_name": evaluation_name,  # function or rubric name
                    "evaluation_type": evaluation_type,
                }

                for k, v in metric_dict.items():
                    if k not in [
                        "function_name",
                        "rubric_name",
                        "metric_name",
                        "type",
                        "name",
                    ]:
                        metric_graph_dict[child_metric][k] = v
                # copy over details of parent metric that aren't already present
                for k, v in parent_metric_dict.items():
                    if k not in metric_graph_dict[child_metric]:
                        metric_graph_dict[child_metric][k] = v
            else:
                # if there is no parent, just add a node by itself
                G.add_node(child_metric)
                metric_graph_dict[child_metric] = {
                    "evaluation_name": evaluation_name,  # function or rubric name
                    "evaluation_type": evaluation_type,
                }
                for k, v in metric_dict.items():
                    if k not in [
                        "function_name",
                        "rubric_name",
                        "metric_name",
                        "type",
                        "name",
                    ]:
                        metric_graph_dict[child_metric][k] = v

                # G.add_edge("root", child_metric)

    # Make string representation with all nodes for error printing in assertion
    graph_string = "Metric Dependencies:"
    for edge in G.edges():
        graph_string += f"\n{'' if edge[1] == 'root' else edge[1]} -> {edge[0]}"

    assert nx.is_directed_acyclic_graph(
        G
    ), "The set of metric dependencies must be acyclic! You have cyclical dependencies. {graph_string}"

    # Set up sequence of evaluations
    # Perform topological sort
    # This is the order in which metrics will be evaluated
    # and the conditions under which they will be evaluated
    topological_order = list(nx.topological_sort(G))
    metric_graph = [metric_graph_dict[node] for node in topological_order]
    return metric_graph


def get_metric_info(single_metric: dict):
    """Input will be a single metric dictionary
    Output will be
    - string representation of metric using json.dumps
    - evaluation_name - function_name or rubric_name
    """
    return json.dumps(single_metric), single_metric.get("name")


def get_parent_metrics(all_metrics: dict, child: dict) -> dict:
    """all_metrics will be a dictionary with keys of "rubric" and "function"
    Both of these map to a list of dictionaries that are derived from evals.yaml
    but that have default values filled in

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
    for requirement in child.get("depends_on", []):
        candidate_parents = []
        allowed_types = ["function", "rubric"]
        if "type" in requirement:
            allowed_types = [requirement["type"]]
        for metric_type in allowed_types:
            for candidate in all_metrics.get(metric_type):
                conditionals = ["last_turn_only", "context_only", "name", "kwargs"]
                matches = True
                for conditional in conditionals:
                    if conditional in requirement and (
                        requirement.get(conditional, None) != candidate.get(conditional)
                    ):
                        matches = False
                if matches:
                    candidate_parents.append(candidate)
        assert (
            len(candidate_parents) > 0
        ), f"We were unable to locate any match for the `depends_on` entry `{json.dumps(requirement,indent=4)}` in the metric `{json.dumps(child,indent=4)}`"
        assert (
            len(candidate_parents) < 2
        ), f"We located more than one match for the `depends_on` entry `{json.dumps(requirement,indent=4)}` in the metric `{json.dumps(child,indent=4)}`. The matches were `{json.dumps(candidate_parents,indent=4)}`. Please add another criterion to disambiguate."
        parents += candidate_parents

    return parents


# for verify installation
# if function_name is defined, rubric
# make sure "function" and "rubric" default to empty lists
# TODO - don't set defaults in "depends_on" to make matching more flexible
# evaluation_name: my_rubric
# evaluation_type: rubric
# metric_name: <
