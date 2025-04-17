from typing import Any, Dict

from pydantic import BaseModel, Field, model_validator


class Command(BaseModel):
    """
    Executable action with its argument.

    Parameters
    ----------
    type : str
        Type of action to execute
    value : str
        The action argument, such as magnitude or sentence to speak
    """

    type: str = Field(..., description="The type of action")
    value: str = Field(..., description="The action argument")

    @model_validator(mode="before")
    @classmethod
    def parse_command_format(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates and transforms the input data.
        If data is a dict with a single key-value pair (e.g., {"move": "wag tail"}),
        it will be transformed to {"type": "move", "value": "wag tail"}.
        """
        if (
            isinstance(data, dict)
            and len(data) == 1
            and "type" not in data
            and "value" not in data
        ):
            key, value = next(iter(data.items()))
            return {"type": key, "value": value}
        return data


class CortexOutputModel(BaseModel):
    """
    Output model for the Cortex LLM responses.

    Parameters
    ----------
    commands : list[Command]
        Sequence of commands to be executed
    """

    commands: list[Command] = Field(..., description="List of actions to execute")
