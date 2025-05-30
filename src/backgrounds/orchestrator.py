import asyncio
import logging
import threading
import typing as T

from backgrounds.base import Background
from runtime.config import RuntimeConfig


class BackgroundOrchestrator:
    """
    Manages the background tasks for the application.
    """

    _config: RuntimeConfig
    _background_threads: T.Dict[str, threading.Thread]

    def __init__(self, config: RuntimeConfig):
        """
        Initialize the BackgroundOrchestrator with the provided configuration.

        Parameters
        ----------
        config : RuntimeConfig
            Configuration object for the runtime.
        """
        self._config = config
        self._background_threads = {}

    def start(self):
        """
        Start background tasks in separate threads.
        """
        for background in self._config.backgrounds:
            if background.name not in self._background_threads:
                thread = threading.Thread(
                    target=self._run_background_loop, args=(background,), daemon=True
                )
                self._background_threads[background.name] = thread
                thread.start()

        return asyncio.Future()

    def _run_background_loop(self, background: Background):
        """
        Thread-based background loop.

        Parameters
        ----------
        background : Background
            The background task to run.
        """
        while True:
            try:
                background.run()
            except Exception as e:
                logging.error(f"Error in background {background.name}: {e}")
