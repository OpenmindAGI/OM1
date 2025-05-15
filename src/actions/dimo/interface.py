from dataclasses import dataclass
from enum import Enum

from actions.base import Interface


class TeslaAction(str, Enum):
    IDLE = "idle"
    LOCK_DOORS = "lock doors"
    UNLOCK_DOOS = "unlock doors"
    OPEN_FRUNK = "open frunk"
    OPEN_TRUNK = "open trunk"


@dataclass
class TeslaInput:
    action: TeslaAction


@dataclass
class DIMOTesla(Interface[TeslaInput, TeslaInput]):
    """
    A Tesla action to be performed by the agent.
    Effect: Allows the agent to interact with a car.
    """

    input: TeslaInput
    output: TeslaInput
