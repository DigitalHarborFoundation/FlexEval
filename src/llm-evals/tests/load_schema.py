import jsonschema
from jsonschema import validate
import json
import yaml

# Define the schema
with open("eval_schema.json", "r") as infile:
    schema = json.load(infile)

# Sample data
with open("../../configuration/evals.yaml", "r") as infile:
    temp = yaml.safe_load(infile)
data = {}
data["evaluation_suite"] = temp["evaluation"]

print(json.dumps(data, indent=4))


# Validate data
validate(instance=data, schema=schema)

# Apply defaults
for prop, prop_details in schema["properties"].items():
    if prop not in data and "default" in prop_details:
        data[prop] = prop_details["default"]
