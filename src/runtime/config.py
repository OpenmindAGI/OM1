import json
import logging
import os
import uuid
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

from .beamer import setup_beamer


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
    cache: bool = False

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

    # Additional configurations
    t_uuid = str(uuid.uuid4())

    global_api_key = raw_config.get("api_key", None)

    if global_api_key is None or global_api_key == "":
        logging.warning(
            "No global API key found in the configuration. Rate limits may apply."
        )

    setup_beamer(global_api_key, t_uuid, raw_config)

    extra_configs = {"uuid": t_uuid, "api_key": global_api_key}

    parsed_config = {
        **raw_config,
        "agent_inputs": [
            load_input(input["type"])(
                config=SensorConfig(
                    **add_extra_configs(input.get("config", {}), extra_configs)
                )
            )
            for input in raw_config.get("agent_inputs", [])
        ],
        "cortex_llm": load_llm(raw_config["cortex_llm"]["type"])(
            config=LLMConfig(
                **add_extra_configs(
                    raw_config["cortex_llm"].get("config", {}), extra_configs
                )
            ),
            output_model=CortexOutputModel,
        ),
        "simulators": [
            load_simulator(simulator["type"])(
                config=SimulatorConfig(
                    name=simulator["type"],
                    **add_extra_configs(simulator.get("config", {}), extra_configs),
                )
            )
            for simulator in raw_config.get("simulators", [])
        ],
        "agent_actions": [
            load_action(
                {
                    **action,
                    "config": add_extra_configs(
                        action.get("config", {}), extra_configs
                    ),
                }
            )
            for action in raw_config.get("agent_actions", [])
        ],
    }

    return RuntimeConfig(**parsed_config)


def add_extra_configs(config: Dict, extra_configs: Dict[str, str]) -> dict:
    """
    Update the runtime configuration with additional configurations.

    Parameters
    ----------
    config : dict
        The runtime configuration to update.
    extra_configs : dict
        Additional configurations to add to the runtime configuration.

    Returns
    -------
    dict
        The updated runtime configuration.
    """
    for key, value in extra_configs.items():
        if key not in config and value is not None:
            config[key] = value
    return config
