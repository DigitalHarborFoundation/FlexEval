import os
from pathlib import Path
import sys
import inspect

import pydantic
import json
import peewee as pw
from classes.BaseModel import BaseModel
from classes.EvalSetRun import EvalSetRun
from classes.Dataset import Dataset
from classes.DatasetRow import DatasetRow
from classes.Turn import Turn
from playhouse.shortcuts import model_to_dict
import copy

from configuration import function_metrics as fm


class TurnMetric(BaseModel):
    """Holds a single metric/property computed based one just ONE turn"""

    id = pw.IntegerField(primary_key=True)

    evalsetrun = pw.ForeignKeyField(EvalSetRun, backref="turnproperties")
    dataset = pw.ForeignKeyField(Dataset, backref="turnproperties")
    datasetrow = pw.ForeignKeyField(DatasetRow, backref="turnproperties")
    turn = pw.ForeignKeyField(Turn, backref="turnproperties")

    metric_definition = pw.TextField()
    metric_function_name = pw.TextField()
    metric_name = pw.TextField()
    metric_value = pw.FloatField()
    metric_kwargs = pw.TextField()
    metric_source = pw.TextField()


def compute_metric(metric_name: str, metric_definition: dict, turn: Turn) -> list:
    # this is NOT a method - it's a function b/c we want it to be able to return multiple metrics, if more than one is returned
    # they share most of the same information though so it's convenient to have them constructed similarly
    # will return a list of dictionaries
    metric_kwargs = json.loads(metric_definition).get("kwargs", None)

    # Check if the function name exists in the global namespace and call it

    if hasattr(fm, metric_name) and hasattr(fm, metric_name):
        metric_function = getattr(fm, metric_name, None)
        metric_source = inspect.getsource(metric_function)

        input_type = inspect.signature(metric_function).parameters.items()[0]
        # conditional depending on the type
        if isinstance(input_type, str):
            # just pass in the content
            metrics_result = metric_function(turn.content, **metric_kwargs)
        elif isinstance(input_type, list):
            # this is on a single turn - pass in the parsed list
            metrics_result = metric_function(json.loads(turn.turn), **metric_kwargs)

        base_result = {
            "turn": turn,
            "metric_definition": metric_definition,
            "metric_function_name": metric_name,
            "metric_kwargs": metric_kwargs,
            "metric_source": metric_source,
        }
        # now deal with output
        if isinstance(metrics_result, float) or isinstance(metrics_result, int):
            result = copy.deepcopy(base_result)
            result["metric_name"] = metric_name
            result["metric_value"] = metrics_result
            return [result]
        elif isinstance(metrics_result, dict):
            result_list = []
            for k, v in metrics_result.items():
                result = copy.deepcopy(base_result)
                result["metric_name"] = k
                result["metric_value"] = float(v)
                result_list.append(result)
            return result_list
        elif isinstance(metrics_result, list):
            result_list = []
            for entry in metrics_result:
                result = copy.deepcopy(base_result)
                result["metric_name"] = entry.get("metric_name", None)
                result["metric_value"] = float(entry.get("metric_value", None))
                result_list.append(result)
            return result_list
