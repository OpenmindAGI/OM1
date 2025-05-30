import time
from dataclasses import dataclass


@dataclass
class BackgroundConfig:
    """
    Configuration class for Background implementations.

    Parameters
    ----------
    **kwargs : dict
        Additional configuration parameters
    """

    def __init__(self, **kwargs):
        # Store any config parameters
        for key, value in kwargs.items():
            setattr(self, key, value)


class Background:
    """
    Base class for background components
    """

    def __init__(self, config: BackgroundConfig):
        """
        Initialize background with configuration

        Parameters
        ----------
        config : BackgroundConfig
            Configuration object for the background
        """
        self.config = config
        self.name = getattr(config, "name", type(self).__name__)

    def run(self) -> None:
        """
        Run the background process.

        This method should be overridden by subclasses to implement specific behavior.
        """
        time.sleep(60)
