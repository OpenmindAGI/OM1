import logging
import time

from backgrounds.base import Background, BackgroundConfig


class ExampleBackground(Background):
    """
    Example background implementation that runs indefinitely.
    """

    def __init__(self, config: BackgroundConfig):
        """
        Initialize the ExampleBackground with configuration.

        Parameters
        ----------
        config : BackgroundConfig
            Configuration object for the background.
        """
        super().__init__(config)
        self.name = getattr(config, "name", "ExampleBackground")

    def run(self) -> None:
        """
        Run the background process.
        This method will run indefinitely, simulating a long-running task.
        """
        while True:
            logging.info(f"Background {self.name} is running... {time.time()}")
            time.sleep(5)
