from pydantic import BaseModel, Field


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


class CortexOutputModel(BaseModel):
    """
    Output model for the Cortex LLM responses.

    Parameters
    ----------
    commands : list[Command]
        Sequence of commands to be executed
    """

    commands: list[Command] = Field(..., description="List of actions to execute")
