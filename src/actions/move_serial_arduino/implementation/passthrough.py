from actions.base import ActionImplementation
from actions.move.interface import MoveInput


class MovePassthroughImplementation(ActionImplementation[MoveInput, MoveInput]):
    """
    A passthrough implementation of the move action. Output is the same as the input.
    """

    async def execute(self, input_interface: MoveInput) -> MoveInput:
        return input_interface
