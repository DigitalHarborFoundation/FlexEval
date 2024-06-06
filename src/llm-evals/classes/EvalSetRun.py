import logging
from datetime import datetime
import peewee as pw
import yaml
import unittest
import os
from pathlib import Path
import sys
from classes.BaseModel import BaseModel
import pydantic
import json
import networkx as nx


class EvalSetRun(BaseModel):
    """Class for running set of evaluations"""

    id = pw.IntegerField(primary_key=True)
    name = pw.CharField(null=True)
    notes = pw.TextField(null=True)
    dataset_files = pw.TextField()  # JSON string
    metrics = pw.TextField()
    do_completion = pw.BooleanField()
    completion_llm = pw.TextField(null=True)  # JSON string
    grader_llm = pw.TextField(null=True)  # JSON string
    model_name = pw.TextField(null=True)  # JSON string
    success = pw.BooleanField(null=True)
    rubrics = pw.TextField(null=True)
    metric_graph = pw.TextField(null=True)  # because it'll be generated after creation
    timestamp = pw.DateTimeField(
        default=datetime.now
    )  # Automatically set to current date and time

    def get_datasets(self) -> list:
        temp = json.loads(self.dataset_files)
        assert isinstance(temp, list), "The `data` entry in evals.yaml must be a list."
        return temp

    def create_metrics_graph(self):
        user_metrics = json.loads(self.metrics)
        # Create a directed graph
        self.G = nx.DiGraph()
        metric_graph_dict = {}
        for metric_type in ["function", "rubric"]:
            if metric_type in user_metrics:
                assert isinstance(
                    user_metrics.get(metric_type), list
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
                            min_value = requirement.get("min_value", None)
                            max_value = requirement.get("max_value", None)
                            parent_metric = requirement.get(
                                "name"
                            )  # + f"[{min_value},{max_value}]"
                            # Add nodes and edges
                            self.G.add_edge(parent_metric, child_metric)
                            metric_graph_dict[child_metric] = {
                                "name": child_metric,
                                "type": metric_type,
                                "kwargs": metric_dict.get("kwargs", {}),
                                "depends_on": metric_dict.get("depends_on", []),
                            }
                    else:
                        # keep this here - we won't evaluate 'root', but if we don't include this, the child
                        self.G.add_node(child_metric)
                        metric_graph_dict[child_metric] = {
                            "name": child_metric,
                            "type": metric_type,
                            "kwargs": metric_dict.get("kwargs", {}),
                            "depends_on": metric_dict.get("depends_on", []),
                        }
                        # G.add_edge("root", child_metric)

        assert nx.is_directed_acyclic_graph(
            self.G
        ), "The set of metric dependencies must be acyclic! You have cyclical dependencies."

        # Set up sequence of evaluations
        # Perform topological sort
        # This is the order in which metrics will be evaluated
        # and the conditions under which they will be evaluated
        topological_order = list(nx.topological_sort(self.G))
        self.metric_graph = json.dumps(
            [metric_graph_dict[node] for node in topological_order]
        )


# # Create the tables

# # Create a new user
# user = User.create(username="john_doe", email="john@example.com")

# # Query all users
# users = User.select()
# for user in users:
#     print(user.username, user.email)

# # Query a single user
# user = User.get(User.username == "john_doe")
# print(user.username, user.email)

# # Update a user's email
# user.email = "john.doe@example.com"
# user.save()

# # Delete a user
# user.delete_instance()

# # Close the database connection
# db.close()
