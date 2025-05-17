import importlib
import typing as T
from enum import Enum

from actions.base import (
    ActionConfig,
    ActionConnector,
    ActionImplementation,
    AgentAction,
    Interface,
)


def describe_action(action_name: str, llm_label: str) -> str:
    interface = None
    action = importlib.import_module(f"actions.{action_name}.interface")
    for _, obj in action.__dict__.items():
        if isinstance(obj, type) and issubclass(obj, Interface) and obj != Interface:
            interface = obj
    if interface is None:
        raise ValueError(f"No interface found for action {action_name}")
    # Get docstring from interface class
    doc = interface.__doc__ or ""
    doc = doc.replace("\n", "")

    # Build type hint descriptions
    hints = {}
    input_interface = T.get_type_hints(interface)["input"]
    for field_name, field_type in T.get_type_hints(input_interface).items():
        if hasattr(field_type, "__origin__") and isinstance(
            field_type.__origin__, type
        ):
            # Handle generic types
            hints[field_name] = str(field_type)
        elif isinstance(field_type, type) and issubclass(field_type, Enum):
            # Handle enums by listing allowed values
            values = [f"'{v.value}'" for v in field_type]
            hints[field_name] = "value={" + f"{', '.join(values)}" + "}"
        else:
            hints[field_name] = f"value={str(field_type)}"

    # Format the full docstring
    type_hints = "\n".join(f"{desc}" for name, desc in hints.items())
    final_description = f"{llm_label.upper()}: {doc}\ntype={llm_label}\n{type_hints}"
    # logging.info(f"final_description:{final_description}")
    # remove indents
    final_description = final_description.replace("    ", "")

    return final_description


def load_action(
    action_config: T.Dict[str, T.Union[str, T.Dict[str, str]]],
) -> AgentAction:
    interface = None
    action = importlib.import_module(f"actions.{action_config['name']}.interface")
    for _, obj in action.__dict__.items():
        if isinstance(obj, type) and issubclass(obj, Interface) and obj != Interface:
            interface = obj
    if interface is None:
        raise ValueError(f"No interface found for action {action_config['name']}")
    if action_config["implementation"] == "passthrough":
        implementation = importlib.import_module("actions.passthrough")
    else:
        implementation = importlib.import_module(
            f"actions.{action_config['name']}.implementation.{action_config['implementation']}"
        )
    connector = importlib.import_module(
        f"actions.{action_config['name']}.connector.{action_config['connector']}"
    )
    implementation_class = None
    connector_class = None
    for _, obj in implementation.__dict__.items():
        if isinstance(obj, type) and issubclass(obj, ActionImplementation):
            implementation_class = obj
    for _, obj in connector.__dict__.items():
        if isinstance(obj, type) and issubclass(obj, ActionConnector):
            connector_class = obj
    if implementation_class is None:
        raise ValueError(
            f"No implementation found for action {action_config['name']} implementation {action_config['implementation']}"
        )
    if connector_class is None:
        raise ValueError(
            f"No connector found for action {action_config['name']} connector {action_config['connector']}"
        )
    config = ActionConfig(**action_config.get("config", {}))
    return AgentAction(
        name=action_config["name"],
        llm_label=action_config["llm_label"],
        interface=interface,
        implementation=implementation_class(config),
        connector=connector_class(config),
    )
