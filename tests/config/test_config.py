import importlib
import os
import sys
from typing import Type
import json5
from jsonschema import Draft7Validator

# === Add project root and src to sys.path ===
current_file = os.path.abspath(__file__)
project_root = os.path.abspath(os.path.join(current_file, "../../../"))
src_path = os.path.join(project_root, "src")
sys.path.insert(0, project_root)  # for `schema/`
sys.path.insert(0, src_path)      # for `actions`, `runtime`, etc.

# === Imports from src and schema ===
from schema.agent_config_schema import agent_config_schema
from actions.base import ActionConnector, ActionImplementation, Interface
from runtime.config import load_input, load_llm, load_simulator


def test_configs():
    config_folder_path = os.path.join(os.path.dirname(__file__), "../../config")
    file_names = [f.name for f in os.scandir(config_folder_path) if f.name.endswith(".json5")]

    # Skip configs that require unavailable dependencies like zenoh
    zenoh_configs = {
        "turtlebot4.json5",
        "unitree_go2.json5",
        "unitree_g1_humanoid.json5",
        "tesla.json5"
    }

    all_errors = []

    for file_name in file_names:
        if file_name in zenoh_configs:
            print(f"⏭️  Skipping {file_name} (depends on zenoh)")
            continue

        try:
            with open(os.path.join(config_folder_path, file_name), "r") as f:
                raw_config = json5.load(f)
        except Exception as e:
            all_errors.append(f"❌ Failed to load {file_name}:\n{str(e)}")
            continue

        # Schema validation
        schema_error = validate_schema(raw_config, agent_config_schema, file_name)
        if schema_error:
            all_errors.append(schema_error)
            continue  # Don't run runtime checks if schema is broken

        # Runtime structural checks
        try:
            agent_inputs = raw_config.get("agent_inputs", [])
            cortex_llm = raw_config.get("cortex_llm", {})
            simulators = raw_config.get("simulators", [])
            agent_actions = raw_config.get("agent_actions", [])

            for input in agent_inputs:
                assert load_input(input["type"]) is not None

            for simulator in simulators:
                assert load_simulator(simulator["type"]) is not None

            for action in agent_actions:
                assert_action_classes_exist(action)

            assert load_llm(cortex_llm["type"]) is not None

        except Exception as e:
            all_errors.append(f"❌ Runtime error in {file_name}:\n{str(e)}")

    if all_errors:
        raise AssertionError("\n\n".join(all_errors))


def validate_schema(instance, schema, file_name):
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: e.path)

    if not errors:
        return None

    messages = [f"- {'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors]
    return f"❌ Schema validation failed for {file_name}:\n" + "\n".join(messages)


def assert_action_classes_exist(action_config):
    action_module = importlib.import_module(f"actions.{action_config['name']}.interface")
    interface = find_subclass_in_module(action_module, Interface)
    assert interface is not None, f"No interface found for action {action_config['name']}"

    if action_config["implementation"] != "passthrough":
        impl_module = importlib.import_module(
            f"actions.{action_config['name']}.implementation.{action_config['implementation']}"
        )
        implementation = find_subclass_in_module(impl_module, ActionImplementation)
        assert implementation is not None, f"No implementation found for action {action_config['name']}"

    connector_module = importlib.import_module(
        f"actions.{action_config['name']}.connector.{action_config['connector']}"
    )
    connector = find_subclass_in_module(connector_module, ActionConnector)
    assert connector is not None, f"No connector found for action {action_config['name']}"


def find_subclass_in_module(module, parent_class: Type) -> Type:
    for _, obj in module.__dict__.items():
        if isinstance(obj, type) and issubclass(obj, parent_class) and obj != parent_class:
            return obj
    return None

