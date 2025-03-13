import importlib
import json
import os
from typing import Type

from actions.base import ActionConnector, ActionImplementation, Interface
from runtime.config import load_input, load_llm, load_simulator


def test_configs():
    """Test that all config files can be loaded."""
    config_folder_path = os.path.join(os.path.dirname(__file__), "../../config")
    files_names = [
        entry.name for entry in os.scandir(config_folder_path) if entry.is_file()
    ]

    for file_name in files_names:
        assert file_name.endswith(".json")
        with open(os.path.join(config_folder_path, file_name), "r") as f:
            raw_config = json.load(f)

        agent_inputs = raw_config.get("agent_inputs", [])
        assert isinstance(agent_inputs, list)

        cortex_llm = raw_config.get("cortex_llm", {})
        assert isinstance(cortex_llm, dict)

        simulators = raw_config.get("simulators", [])
        assert isinstance(simulators, list)

        agent_actions = raw_config.get("agent_actions", [])
        assert isinstance(agent_actions, list)

        for input in agent_inputs:
            assert load_input(input["type"]) is not None

        for simulator in simulators:
            assert load_simulator(simulator["type"]) is not None

        for action in agent_actions:
            assert_action_classes_exist(action)

        assert load_llm(cortex_llm["type"]) is not None


def assert_action_classes_exist(action_config):
    """Assert that all required classes for an action exist without instantiating them."""
    # Check interface exists
    action_module = importlib.import_module(
        f"actions.{action_config['name']}.interface"
    )
    interface = find_subclass_in_module(action_module, Interface)
    assert (
        interface is not None
    ), f"No interface found for action {action_config['name']}"

    # Check implementation exists
    if action_config["implementation"] != "passthrough":
        impl_module = importlib.import_module(
            f"actions.{action_config['name']}.implementation.{action_config['implementation']}"
        )
        implementation = find_subclass_in_module(impl_module, ActionImplementation)
        assert (
            implementation is not None
        ), f"No implementation found for action {action_config['name']}"

    # Check connector exists
    connector_module = importlib.import_module(
        f"actions.{action_config['name']}.connector.{action_config['connector']}"
    )
    connector = find_subclass_in_module(connector_module, ActionConnector)
    assert (
        connector is not None
    ), f"No connector found for action {action_config['name']}"


def find_subclass_in_module(module, parent_class: Type) -> Type:
    """Find a subclass of parent_class in the given module."""
    for _, obj in module.__dict__.items():
        if (
            isinstance(obj, type)
            and issubclass(obj, parent_class)
            and obj != parent_class
        ):
            return obj
    return None
