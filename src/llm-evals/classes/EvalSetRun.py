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
import helpers


class EvalSetRun(BaseModel):
    """Class for running set of evaluations"""

    id = pw.IntegerField(primary_key=True)
    name = pw.CharField(null=True)
    notes = pw.TextField(null=True)
    dataset_files = pw.TextField()  # JSON string
    metrics = pw.TextField()
    metrics_graph_ordered_list = pw.TextField()
    do_completion = pw.BooleanField()
    completion_llm = pw.TextField(null=True)  # JSON string
    grader_llm = pw.TextField(null=True)  # JSON string
    model_name = pw.TextField(null=True)  # JSON string
    success = pw.BooleanField(null=True)
    rubrics = pw.TextField(null=True)
    timestamp = pw.DateTimeField(
        default=datetime.now
    )  # Automatically set to current date and time

    def get_datasets(self) -> list:
        temp = json.loads(self.dataset_files)
        assert isinstance(temp, list), "The `data` entry in evals.yaml must be a list."
        return temp


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
