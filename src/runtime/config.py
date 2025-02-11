import json
import os
from dataclasses import dataclass
from typing import List, Optional

from actions import load_action
from actions.base import AgentAction
from inputs import load_input
from inputs.base import Sensor, SensorConfig
from llm import LLM, LLMConfig, load_llm
from llm.output_model import CortexOutputModel
from runtime.robotics import load_unitree
from simulators import load_simulator
from simulators.base import Simulator


@dataclass
class RuntimeConfig:
    """
    Runtime configuration container.

    Parameters
    ----------
    hertz : float
        The frequency at which the runtime loop operates
    name : str
        Unique identifier for this configuration
    system_prompt : str
        System prompt used for LLM initialization
    agent_inputs : List[Sensor]
        List of input components for gathering agent data
    cortex_llm : LLM[CortexOutputModel]
        Language model configuration for the agent's cognitive processing
    agent_actions : List[AgentAction]
        List of available actions the agent can perform
    simulators : List[Simulator]
        List of simulation components for environment modeling
    unitree_ethernet : str
        Ethernet adapter name for Unitree robot communication
    """

    hertz: float
    name: str
    system_prompt_base: str
    system_governance: str
    system_prompt_examples: str
    agent_inputs: List[Sensor]
    cortex_llm: LLM[CortexOutputModel]
    agent_actions: List[AgentAction]
    simulators: List[Simulator]

    # unitree
    unitree_ethernet: Optional[str] = None


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

    parsed_config = {
        **raw_config,
        "agent_inputs": [
            load_input(input["type"])(config=SensorConfig(**input.get("config", {})))
            for input in raw_config.get("agent_inputs", [])
        ],
        "cortex_llm": load_llm(raw_config["cortex_llm"]["type"])(
            config=LLMConfig(**raw_config["cortex_llm"].get("config", {})),
            output_model=CortexOutputModel,
        ),
        "simulators": [
            load_simulator(simulator["type"])()
            for simulator in raw_config.get("simulators", [])
        ],
        "agent_actions": [
            load_action(action) for action in raw_config.get("agent_actions", [])
        ],
    }

    return RuntimeConfig(**parsed_config)
