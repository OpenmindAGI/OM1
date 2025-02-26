from dataclasses import dataclass

from actions.base import Interface


@dataclass
class SpeakInput:
    action: str


@dataclass
class Speak(Interface[SpeakInput, SpeakInput]):
    """
    Words to be spoken by the agent.

    Effect: Allows the agent to speak.
    """

    input: SpeakInput
    output: SpeakInput
