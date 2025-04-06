# This can be empty

# Import and expose the mapping plugin
from src.simulators.plugins.SimpleMapper import SimpleMapper
from src.simulators.plugins.MapGeneratorPlugin import MapGeneratorPlugin

__all__ = ['SimpleMapper', 'MapGeneratorPlugin']
