import importlib
import inspect
import logging
import os
import typing as T

from simulators.base import Simulator, SimulatorConfig

__all__ = ["Simulator", "SimulatorConfig", "load_simulator"]


def load_simulator(sim_type: str) -> T.Type[Simulator]:
    """
    Load a simulator from the simulators directory.

    Parameters
    ----------
    sim_type : str
        The type/name of the simulator to load.

    Returns:
    ---------
    T.Type[Simulator]
        An instance of the simulator.
    """
    # Get all files in plugins directory
    plugins_dir = os.path.join(os.path.dirname(__file__), "plugins")
    plugin_files = [f[:-3] for f in os.listdir(plugins_dir) if f.endswith(".py")]

    # Import all simulators and find Simulator subclasses
    simulator_classes = {}
    for plugin in plugin_files:
        simulator = importlib.import_module(f"simulators.plugins.{plugin}")
        for name, obj in inspect.getmembers(simulator):
            if inspect.isclass(obj) and issubclass(obj, Simulator) and obj != Simulator:
                simulator_classes[name] = obj

    logging.debug(f"Simulator classes: {simulator_classes}")

    # Find requested simulator class
    if sim_type not in simulator_classes:
        raise ValueError(f"Simulator {sim_type} not found")

    return simulator_classes[sim_type]
