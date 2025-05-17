import logging
import threading
import time
from queue import Queue
from typing import Callable, Optional

import zenoh


class ZenohListenerProvider:
    """
    Listener provider for subscribing messages using a Zenoh session.

    This class manages a Zenoh session, a message queue, and a worker thread that
    continuously listens to messages to a specified topic.
    """

    def __init__(self, topic: str = "speech"):
        """
        Initialize the Zenoh Listener provider and create a Zenoh session.

        Parameters
        ----------
        topic : str, optional
            The topic on which to subscribe messages (default is "speech").
        """
        try:
            self.session = zenoh.open(zenoh.Config())
            logging.info("Zenoh client opened")
        except Exception as e:
            logging.error(f"Error opening Zenoh client: {e}")

        self.sub_topic = topic

        # Pending message queue and threading constructs
        self._pending_messages = Queue()
        self._lock = threading.Lock()
        self.running: bool = False
        self._thread: Optional[threading.Thread] = None

    def register_message_callback(self, message_callback: Optional[Callable]):
        """
        Register a callback function for processing incoming messages.

        Parameters
        ----------
        message_callback : Callable
            The function that will be called with each incoming Zenoh sample.
        """
        if self.session is not None:
            self.session.declare_subscriber(self.sub_topic, message_callback)
        else:
            logging.error("Cannot register callback; Zenoh session is not available.")

    def start(self):
        """
        Start the listener provider by launching the background thread.
        """
        if self.running:
            return

        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logging.info("Zenoh Listener Provider started")

    def _run(self):
        """
        Internal method to run the provider's main processing loop.

        This method runs in a separate thread and handles the continuous processing
        of zenoh messages.
        """
        while self.running:
            try:
                time.sleep(0.1)
            except Exception as e:
                logging.error(f"Zenoh Listener Provider error: {e}")

    def stop(self):
        """
        Stop the listener provider and clean up resources.

        Stops the background thread and closes the Zenoh session.

        Notes
        -----
        The thread join operation uses a 5-second timeout to prevent hanging.
        """
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        if self.session is not None:
            self.session.Close()
