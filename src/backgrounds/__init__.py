import importlib
import inspect
import logging
import os
import typing as T

from backgrounds.base import Background


def load_background(background_name: str) -> T.Type[Background]:
    """
    Load a background from the backgrounds directory.

    Parameters
    ----------
    background_name : str
        The name of the background to load.

    Returns:
    ---------
    T.Type[Background]
        A class (type) of the background.
    """
    # Get all files in plugins directory
    plugins_dir = os.path.join(os.path.dirname(__file__), "plugins")
    plugin_files = [f[:-3] for f in os.listdir(plugins_dir) if f.endswith(".py")]

    # Import all backgrounds and find Background subclasses
    background_classes = {}
    for plugin in plugin_files:
        background = importlib.import_module(f"backgrounds.plugins.{plugin}")
        for name, obj in inspect.getmembers(background):
            if (
                inspect.isclass(obj)
                and issubclass(obj, Background)
                and obj != Background
            ):
                background_classes[name] = obj

    logging.debug(f"Background classes: {background_classes}")

    # Find requested background class
    if background_name not in background_classes:
        raise ValueError(f"Background {background_name} not found")

    return background_classes[background_name]
