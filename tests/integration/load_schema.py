import json
import os

import jsonschema
import yaml
from jsonschema import validate

# Define the schema
with open("src/flexeval/eval_schema.json", "r") as infile:
    schema = json.load(infile)

# Sample data
with open("src/flexeval/configuration/evals.yaml", "r") as infile:
    temp = yaml.safe_load(infile)
data = {}
data["evaluation_suite"] = temp["evaluation"]

print(json.dumps(data, indent=4))


# Validate data
validate(instance=data, schema=schema)


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

        # Apply special rule only within the "function" list of the "metrics"
        if path == ["evaluation_suite", "metrics", "function"]:
            if "function_name" in data and "metric_name" not in data:
                data["metric_name"] = data["function_name"]

        return data

    if isinstance(data, list) and "items" in schema:
        # Process lists by applying defaults to each item
        item_schema = schema["items"]
        # Apply defaults to each item in the list, passing along the path
        return [apply_defaults(item_schema, item, path) for item in data]

    return data


# Apply defaults
data = apply_defaults(schema, data)

print(json.dumps(data, indent=4))
