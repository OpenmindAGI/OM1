from dataclasses import dataclass
from enum import Enum

from actions.base import Interface


class MovementAction(str, Enum):
    STAND_STILL = "stand still"
    RUN = "run"
    WALK_FORWARD = "walk forward"
    WALK_BACKWARD = "walk backward"
    TURN_LEFT = "turn left"
    TURN_RIGHT = "turn right"
    LOOK_LEFT = "look left"
    LOOK_RIGHT = "look right"
    MOVE_LEFT = "move left"
    MOVE_RIGHT = "move right"


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
