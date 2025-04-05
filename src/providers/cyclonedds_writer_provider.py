import logging
import threading
from dataclasses import dataclass
from queue import Empty, Queue
from typing import Optional

from cyclonedds.domain import Domain, DomainParticipant
from cyclonedds.idl import IdlStruct
from cyclonedds.pub import DataWriter
from cyclonedds.topic import Topic

CycloneDDSInterfaceConfig = """<?xml version="1.0" encoding="UTF-8" ?>
    <CycloneDDS>
        <Domain>
            <General>
            <Interfaces>
                <NetworkInterface name="$__IF_NAME__$" priority="default" multicast="default" />
            </Interfaces>
            </General>
            <Discovery>
            <EnableTopicDiscoveryEndpoints>true</EnableTopicDiscoveryEndpoints>
            </Discovery>
        </Domain>
    </CycloneDDS>"""

CycloneDDSAutoInterfaceConfig = """<?xml version="1.0" encoding="UTF-8" ?>
    <CycloneDDS>
        <Domain>
            <General>
            <Interfaces>
                <NetworkInterface autodetermine=\"true\" priority="default" multicast="default" />
            </Interfaces>
            </General>
            <Discovery>
            <EnableTopicDiscoveryEndpoints>true</EnableTopicDiscoveryEndpoints>
            </Discovery>
        </Domain>
    </CycloneDDS>"""


# Define a message datatype with one member, data, with as type 'string'
@dataclass
class SpeechData(IdlStruct, typename="SpeechData.Msg"):
    data: str


class CycloneDDSWriterProvider:
    """
    Writer provider for sending messages using a CycloneDDS session

    This class manages a CycloneDDS DomainParticipant, Topic, DataWriter, a message queue, and a worker thread that
    continuously publishes queued messages to a specified topic.
    """

    def __init__(
        self, domainID: int = 0, topic: str = "speech", networkInterface: str = None
    ):
        """
        Initialize the CycloneDDS publisher provider and create a CycloneDDS DomainParticipant, Topic, and DataWriter.

        Parameters
        ----------
        topic : str, optional
            The topic on which to publish messages (default is "speech").
        """
        if networkInterface is not None:
            self.config = CycloneDDSInterfaceConfig.replace(
                "$__IF_NAME__$", networkInterface
            )
            logging.info(
                f"CycloneDDSWriter: Using CycloneDDS network interface {networkInterface}"
            )
        else:
            self.config = CycloneDDSAutoInterfaceConfig
            logging.info(
                "CycloneDDSWriter: No network interface specified. Using autodetermine."
            )

        self.id = domainID
        logging.info(f"CycloneDDSWriter: Using Domain ID {self.id} ")

        try:
            self.dm = Domain(domain_id=self.id, config=self.config)
            logging.info("CycloneDDSWriter: CycloneDDS Domain created")
        except Exception as e:
            logging.error(f"CycloneDDSWriter: Error creating CycloneDDS Domain: {e}")
            self.dm = None

        try:
            self.dp = DomainParticipant(domain_id=self.id)
            logging.info("CycloneDDSWriter: CycloneDDS DomainParticipant created")
        except Exception as e:
            logging.error(
                f"CycloneDDSWriter: Error creating CycloneDDS DomainParticipant: {e}"
            )
            self.dp = None

        try:
            self.tp = Topic(
                domain_participant=self.dp, topic_name=topic, data_type=SpeechData
            )
            logging.info("CycloneDDSWriter: CycloneDDS Topic created")
        except Exception as e:
            logging.error(f"CycloneDDSWriter: Error creating CycloneDDS Topic: {e}")
            self.tp = None

        try:
            self.dw = DataWriter(publisher_or_participant=self.dp, topic=self.tp)
            logging.info("CycloneDDS DataWriter created")
        except Exception as e:
            logging.error(f"Error creating CycloneDDS DataWriter: {e}")
            self.dw = None

        # Pending message queue and threading constructs
        self._pending_messages = Queue()
        self._lock = threading.Lock()
        self.running: bool = False
        self._thread: Optional[threading.Thread] = None

    def add_pending_message(self, text: str):
        """
        Create a SpeechData message from the provided text and add it to the queue.

        Parameters
        ----------
        text : str
            The textual content to be published as a message.
        """
        msg = SpeechData(data=text)
        logging.info(f"Queueing message: {text}")
        self._pending_messages.put(msg)

    def _publish_message(self, msg: SpeechData):
        """
        Publish a single SpeechData message using CycloneDDS.

        Parameters
        ----------
        msg : SpeechData
            The message to be published.
        """
        # Attempt to write the message with a timeout of 0.5 seconds

        if self.dw is None:
            logging.info("No open CycloneDDS DataWriter, returning")
            return
        logging.info("Publishing message: {} ".format(msg))
        self.dw.write(msg)

    def start(self):
        """
        Start the publisher provider by launching the processing thread.
        """
        if self.running:
            return

        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logging.info("CycloneDDS Writer Provider started")

    def _run(self):
        """
        Internal loop that processes and publishes pending messages.
        """
        while self.running:
            try:
                # Wait up to 0.5 seconds for a message.
                msg = self._pending_messages.get(timeout=0.5)
                self._publish_message(msg)
            except Empty:
                continue
            except Exception as e:
                logging.exception("Exception in CycloneDDS Writer thread: %s", e)

    def stop(self):
        """
        Stop the writer provider and clean up resources.
        """
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        logging.info("CycloneDDS Writer Provider stopped")
