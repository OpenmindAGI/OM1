import time
import typing as T
from abc import ABC, abstractmethod
from dataclasses import dataclass

IT = T.TypeVar("IT")
OT = T.TypeVar("OT")


@dataclass
class ActionConfig:
    """
    Configuration class for Action implementations.

    Parameters
    ----------
    **kwargs : dict
        Additional configuration parameters
    """

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


@dataclass
class Interface(T.Generic[IT, OT]):
    """
    An interface for a action.
    """

    input: IT
    output: OT


class ActionImplementation(ABC, T.Generic[IT, OT]):
    def __init__(self, config: ActionConfig):
        self.config = config
        pass

    @abstractmethod
    async def execute(self, input_protocol: IT) -> OT:
        pass

    # Fallback code that will not normally run, but is here
    # for safety. In general, the specific actions e.g.
    # /actions/move/connector/ros2.py will provide their
    # own implementions
    def tick(self) -> None:
        # fallback setting, specific sleep value should not matter.
        time.sleep(60)


class ActionConnector(ABC, T.Generic[OT]):
    def __init__(self, config: ActionConfig):
        self.config = config

    @abstractmethod
    async def connect(self, input_protocol: OT) -> None:
        pass

    def tick(self) -> None:
        time.sleep(60)


@dataclass
class AgentAction:
    """Base class for agent actions"""

    name: str
    llm_label: str
    interface: T.Type[Interface]
    implementation: ActionImplementation
    connector: ActionConnector
