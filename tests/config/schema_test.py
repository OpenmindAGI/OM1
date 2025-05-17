import json
import os

import json5
import pytest
from jsonschema import ValidationError, validate

json_dir = os.path.join(os.path.dirname(__file__), "../../config")


@pytest.fixture(scope="session")
def json_schema():
    schema_path = os.path.join(json_dir, "schema/schema.json")
    with open(schema_path) as f:
        return json.load(f)


def get_all_json_files():
    return [
        os.path.join(json_dir, f) for f in os.listdir(json_dir) if f.endswith(".json5")
    ]


@pytest.mark.parametrize("json_file", get_all_json_files())
def test_json_file_valid(json_file, json_schema):
    with open(json_file) as f:
        data = json5.load(f)
    try:
        validate(instance=data, schema=json_schema)
    except ValidationError as e:
        pytest.fail(f"{json_file} failed validation: {e.message}")
