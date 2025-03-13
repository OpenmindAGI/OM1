from dataclasses import dataclass
from enum import Enum

from actions.base import Interface


class EmotionAction(str, Enum):
    HAPPY = "happy"
    SAD = "sad"
    MAD = "mad"
    CURIOUS = "curious"


@dataclass
class EmotionInput:
    action: EmotionAction


@dataclass
class Emotion(Interface[EmotionInput, EmotionInput]):
    """
    An emotion to be performed by the agent.

    Effect: Allows the agent to express emotions.
    """

    input: EmotionInput
    output: EmotionInput
