from dataclasses import dataclass
from enum import Enum

from actions.base import Interface


class MovementAction(str, Enum):
    TURN_LEFT = "turn left"
    TURN_RIGHT = "turn right"
    MOVE_FORWARDS = "move forwards"
    STAND_STILL = "stand still"


@dataclass
class MoveInput:
    action: MovementAction


@dataclass
class Move(Interface[MoveInput, MoveInput]):
    """
    A movement to be performed by the agent.
    Effect: Allows the agent to move.
    """

    input: MoveInput
    output: MoveInput
