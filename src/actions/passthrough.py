import typing as T

from actions.base import ActionImplementation

R = T.TypeVar("R")


class PassthroughAction(ActionImplementation[R, R]):
    async def execute(self, interface: R) -> R:
        """Return the input with no additional action implementation logic."""
        return interface
