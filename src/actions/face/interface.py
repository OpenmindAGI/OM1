from dataclasses import dataclass
from enum import Enum

from actions.base import Interface


class FaceAction(str, Enum):
    CRY = "cry"
    SMILE = "smile"
    FROWN = "frown"
    THINK = "think"
    JOY = "joy"


@dataclass
class FaceInput:
    action: FaceAction


@dataclass
class Face(Interface[FaceInput, FaceInput]):
    """
    A facial expression to be performed by the agent.
    Effect: Shows a given facial expression.
    """

    input: FaceInput
    output: FaceInput
