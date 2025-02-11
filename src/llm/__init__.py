import importlib
import inspect
import os
import typing as T

from pydantic import BaseModel

from providers.io_provider import IOProvider

R = T.TypeVar("R")


class LLMConfig(BaseModel):
    """
    Configuration class for Language Learning Models.

    Parameters
    ----------
    base_url : str, optional
        Base URL for the LLM API endpoint
    api_key : str, optional
        Authentication key for the LLM service
    model : str, optional
        Name of the LLM model to use
    """

    base_url: T.Optional[str] = None
    api_key: T.Optional[str] = None
    model: T.Optional[str] = None


class LLM(T.Generic[R]):
    """
    Base class for Language Learning Model implementations.

    Generic interface for implementing LLM clients with type-safe responses.

    Parameters
    ----------
    output_model : Type[R]
        Type specification for model responses
    config : LLMConfig, optional
        Configuration settings for the LLM

    """

    def __init__(self, output_model: T.Type[R], config: T.Optional[LLMConfig]):
        # Set up the LLM configuration
        self._config = config

        # Set up the output model
        self._output_model = output_model

        # Set up the IO provider
        self.io_provider = IOProvider()

    async def ask(self, prompt: str) -> R:
        """
        Send a prompt to the LLM and receive a typed response.

        Parameters
        ----------
        prompt : str
            Input text to send to the model

        Returns
        -------
        R
            Response matching the output_model type specification

        Raises
        ------
        NotImplementedError
            Must be implemented by subclasses
        """
        raise NotImplementedError


def load_llm(llm_name: str) -> T.Type[LLM]:
    """
    Dynamically load an LLM implementation from the plugins directory.

    Parameters
    ----------
    llm_name : str
        Name of the LLM implementation class to load

    Returns
    -------
    Type[LLM]
        LLM class implementation

    Raises
    ------
    ValueError
        If requested LLM implementation is not found
    """
    # Get all files in plugins directory
    plugins_dir = os.path.join(os.path.dirname(__file__), "plugins")
    plugin_files = [f[:-3] for f in os.listdir(plugins_dir) if f.endswith(".py")]

    # Import all plugin actions and find LLM subclasses
    llm_classes = {}
    for plugin in plugin_files:
        action = importlib.import_module(f"llm.plugins.{plugin}")
        for name, obj in inspect.getmembers(action):
            if inspect.isclass(obj) and issubclass(obj, LLM) and obj != LLM:
                llm_classes[name] = obj

    # Find requested input class
    if llm_name not in llm_classes:
        raise ValueError(f"LLM type {llm_name} not found")

    return llm_classes[llm_name]
