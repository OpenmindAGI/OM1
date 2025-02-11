import time
from dataclasses import dataclass
from typing import List

from llm.output_model import Command


@dataclass
class Simulator:
    """
    Base class for simulation components
    """

    name: str

    def __init__(self, name: str):
        self.name = name

    def sim(self, commands: List[Command]) -> None:
        """
        Simulate the environment with the given commands
        """
        pass

    def tick(self) -> None:
        """
        Run the simulator for one tick

        Note: This method should not block the event loop.
        """
        time.sleep(60)
        pass
