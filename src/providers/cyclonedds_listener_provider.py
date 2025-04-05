import logging
import threading
import time
from queue import Queue
from typing import Callable, Optional

from cyclonedds.core import Listener
from cyclonedds.domain import Domain, DomainParticipant
from cyclonedds.internal import InvalidSample
from cyclonedds.sub import DataReader
from cyclonedds.topic import Topic

from providers.cyclonedds_writer_provider import (
    CycloneDDSAutoInterfaceConfig,
    CycloneDDSInterfaceConfig,
    SpeechData,
)


class CycloneDDSListenerProvider:
    """
    Listener provider for reading messages using CycloneDDS.

    This class manages the CycloneDDS DomainParticipant, Topic, DataReader, a message queue, and a worker thread that
    continuously listens to messages to a specified topic.
    """

    def __init__(
        self,
        domainID: int = 0,
        topic: str = "speech",
        networkInterface: str = None,
        message_callback: Optional[Callable] = None,
    ):
        """
        Initialize the CycloneDDS reader provider and the DomainParticipant, Topic, DataReader

        Parameters
        ----------
        topic : str, optional
            The topic on which to subscribe messages (default is "speech").
        """
        if networkInterface is not None:
            self.config = CycloneDDSInterfaceConfig.replace(
                "$__IF_NAME__$", networkInterface
            )
            logging.info(
                f"CycloneDDSListener: Using CycloneDDS network interface {networkInterface}"
            )
        else:
            self.config = CycloneDDSAutoInterfaceConfig
            logging.info(
                "CycloneDDSListener: No network interface specified. Using autodetermine."
            )

        self.id = domainID
        logging.info(f"CycloneDDSListener: Using Domain ID {self.id} ")

        try:
            self.dm = Domain(domain_id=self.id, config=self.config)
            logging.info("CycloneDDSListener: CycloneDDS Domain created")
        except Exception as e:
            logging.error(f"CycloneDDSListener: Error creating CycloneDDS Domain: {e}")
            self.dm = None

        try:
            self.dp = DomainParticipant(domain_id=self.id)
            logging.info("CycloneDDSListener: CycloneDDS DomainParticipant created")
        except Exception as e:
            logging.error(
                f"CycloneDDSListener: Error creating CycloneDDS DomainParticipant: {e}"
            )
            self.dp = None

        try:
            self.tp = Topic(
                domain_participant=self.dp, topic_name=topic, data_type=SpeechData
            )
            logging.info("CycloneDDSListener: CycloneDDS Topic created")
        except Exception as e:
            logging.error(f"CycloneDDSListener: Error creating CycloneDDS Topic: {e}")
            self.tp = None

        self.message_callback = message_callback

        try:
            self.listener = Listener(on_data_available=self._onDataAvailable)
            logging.info("CycloneDDSListener: CycloneDDS Listener created")
        except Exception as e:
            logging.error(
                f"CycloneDDSListener: Error creating CycloneDDS Listener: {e}"
            )
            self.tp = None

        try:
            self.dr = DataReader(
                subscriber_or_participant=self.dp, topic=self.tp, listener=self.listener
            )
            logging.info("CycloneDDS DataReader created")
        except Exception as e:
            logging.error(f"Error creating CycloneDDS DataReader: {e}")
            self.dr = None

        # Pending message queue and threading constructs
        self._pending_messages = Queue()
        self._lock = threading.Lock()
        self.running: bool = False
        self._thread: Optional[threading.Thread] = None

    def _onDataAvailable(self, reader: DataReader):
        """
        Callback function for processing incoming messages.
        """

        samples = []
        try:
            samples = reader.take(1)
        except Exception as e:
            logging.error(f"No data taken. Error: {e}")

        if samples is None:
            return

        # check invalid sample
        sample = samples[0]
        if isinstance(sample, InvalidSample):
            return

        if self.message_callback is not None:
            self.message_callback(sample.data)

    def start(self):
        """
        Start the reader provider by launching the background thread.
        """
        if self.running:
            return

        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logging.info("CycloneDDS Reader Provider started")

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
                logging.error(f"CycloneDDS Reader Provider error: {e}")

    def stop(self):
        """
        Stop the reader provider and clean up resources.

        Stops the background thread and closes the Zenoh session.

        Notes
        -----
        The thread join operation uses a 5-second timeout to prevent hanging.
        """
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
