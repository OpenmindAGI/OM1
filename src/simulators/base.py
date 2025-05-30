import time
from dataclasses import dataclass
from typing import List

from llm.output_model import Action


@dataclass
class SimulatorConfig:
    """
    Configuration class for Simulator implementations.

    Parameters
    ----------
    **kwargs : dict
        Additional configuration parameters
    """

    def __init__(self, **kwargs):
        # Store any config parameters
        for key, value in kwargs.items():
            setattr(self, key, value)


class Simulator:
    """
    Base class for simulation components
    """

    def __init__(self, config: SimulatorConfig):
        """
        Initialize simulator with configuration

        Parameters
        ----------
        config : SimulatorConfig
            Configuration object for the simulator
        """
        self.config = config
        self.name = getattr(config, "name", "Simulator")

    def sim(self, actions: List[Action]) -> None:
        """
        Simulate the environment with the given actions
        """
        pass

    def tick(self) -> None:
        """
        Run the simulator for one tick

        Note: This method should not block the event loop.
        """
        time.sleep(60)
        pass
