import json
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from actions import load_action
from actions.base import AgentAction
from inputs import load_input
from inputs.base import Sensor, SensorConfig
from llm import LLM, LLMConfig, load_llm
from llm.output_model import CortexOutputModel
from runtime.robotics import load_unitree
from simulators import load_simulator
from simulators.base import Simulator, SimulatorConfig


@dataclass
class RuntimeConfig:
    """Runtime configuration for the agent."""

    hertz: float
    name: str
    system_prompt_base: str
    system_governance: str
    system_prompt_examples: str
    agent_inputs: List[Sensor]
    cortex_llm: LLM
    simulators: List[Simulator]
    agent_actions: List[AgentAction]

    # Optional API key for the runtime configuration
    api_key: Optional[str] = None

    @classmethod
    def load(cls, config_name: str) -> "RuntimeConfig":
        """Load a runtime configuration from a file."""
        return load_config(config_name)


def load_config(config_name: str) -> RuntimeConfig:
    """
    Load and parse a runtime configuration from a JSON file.

    Parameters
    ----------
    config_name : str
        Name of the configuration file (without .json extension)

    Returns
    -------
    RuntimeConfig
        Parsed runtime configuration object

    Raises
    ------
    FileNotFoundError
        If the configuration file does not exist
    json.JSONDecodeError
        If the configuration file contains invalid JSON
    KeyError
        If required configuration fields are missing
    ImportError
        If component types specified in config cannot be imported
    ValueError
        If configuration values are invalid (e.g., negative hertz)
    """
    config_path = os.path.join(
        os.path.dirname(__file__), "../../config", config_name + ".json"
    )

    with open(config_path, "r") as f:
        raw_config = json.load(f)

    # Load Unitree robot communication channel
    load_unitree(raw_config)

    global_api_key = raw_config.get("api_key", None)
    if global_api_key is None or global_api_key == "":
        logging.warning(
            "No global API key found in the configuration. Rate limits may apply."
        )

    parsed_config = {
        **raw_config,
        "agent_inputs": [
            load_input(input["type"])(
                config=SensorConfig(
                    **add_api_key(input.get("config", {}), global_api_key)
                )
            )
            for input in raw_config.get("agent_inputs", [])
        ],
        "cortex_llm": load_llm(raw_config["cortex_llm"]["type"])(
            config=LLMConfig(
                **add_api_key(
                    raw_config["cortex_llm"].get("config", {}), global_api_key
                )
            ),
            output_model=CortexOutputModel,
        ),
        "simulators": [
            load_simulator(simulator["type"])(
                config=SimulatorConfig(
                    name=simulator["type"],
                    **add_api_key(simulator.get("config", {}), global_api_key),
                )
            )
            for simulator in raw_config.get("simulators", [])
        ],
        "agent_actions": [
            load_action(
                {
                    **action,
                    "config": add_api_key(action.get("config", {}), global_api_key),
                }
            )
            for action in raw_config.get("agent_actions", [])
        ],
    }

    return RuntimeConfig(**parsed_config)


def add_api_key(config: Dict, global_api_key: Optional[str]) -> dict:
    """
    Add an API key to a runtime configuration.

    Parameters
    ----------
    config : dict
        The runtime configuration to update.
    api_key : str
        The API key to add.

    Returns
    -------
    dict
        The updated runtime configuration.
    """
    if "api_key" not in config and global_api_key is not None:
        config["api_key"] = global_api_key
    return config
