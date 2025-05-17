import asyncio
import logging
import time
from dataclasses import dataclass
from queue import Empty, Queue
from typing import List, Optional

from inputs.base import SensorConfig
from inputs.base.loop import FuserInput
from providers.io_provider import IOProvider
from providers.rplidar_provider import RPLidarProvider


@dataclass
class Message:
    """
    Container for timestamped messages.

    Parameters
    ----------
    timestamp : float
        Unix timestamp of the message
    message : str
        Content of the message
    """

    timestamp: float
    message: str


class RPLidar(FuserInput[str]):
    """
    RPLidar input handler.

    A class that processes RPLidar inputs and generates text descriptions.
    It maintains an internal buffer of processed messages.
    """

    def __init__(self, config: SensorConfig = SensorConfig()):
        super().__init__(config)

        # Track IO
        self.io_provider = IOProvider()

        # Buffer for storing the final output
        self.messages: List[Message] = []

        # Buffer for storing messages
        self.message_buffer: Queue[str] = Queue()

        logging.info(f"Config: {self.config}")

        # Initialize RPLidar Provider based on .json5 config file
        serial_port = getattr(self.config, "serial_port", None)
        use_zenoh = getattr(self.config, "use_zenoh", False)
        URID = ""
        if use_zenoh:
            # probably a turtlebot
            URID = getattr(self.config, "URID")
            logging.info(f"RPLidar using Zenoh and URID: {URID}")
        half_width_robot = getattr(self.config, "half_width_robot", 0.20)
        angles_blanked = getattr(self.config, "angles_blanked", [])
        max_relevant_distance = getattr(self.config, "max_relevant_distance", 1.1)
        sensor_mounting_angle = getattr(self.config, "sensor_mounting_angle", 180.0)

        self.lidar: RPLidarProvider = RPLidarProvider(
            False,  # wait= this is the one and only place we init this driver
            serial_port,
            half_width_robot,
            angles_blanked,
            max_relevant_distance,
            sensor_mounting_angle,
            URID,
            use_zenoh,
        )

        self.lidar.start()

        self.descriptor_for_LLM = "Here is information about objects and walls around you, to plan your movements and avoid bumping into things."

    async def _poll(self) -> Optional[str]:
        """
        Poll for new messages from the RPLidar Provider.

        Checks the message buffer for new messages with a brief delay
        to prevent excessive CPU usage.

        Returns
        -------
        Optional[str]
            The next message from the buffer if available, None otherwise
        """
        await asyncio.sleep(0.2)
        # logging.info("LIDAR message poll")
        try:
            return self.lidar.lidar_string
        except Empty:
            return None

    async def _raw_to_text(self, raw_input: str) -> Message:
        """
        Process raw input to generate a timestamped message.

        Creates a Message object from the raw input string, adding
        the current timestamp.

        Parameters
        ----------
        raw_input : str
            Raw input string to be processed

        Returns
        -------
        Message
            A timestamped message containing the processed input
        """
        return Message(timestamp=time.time(), message=raw_input)

    async def raw_to_text(self, raw_input: Optional[str]):
        """
        Convert raw input to text and update message buffer.

        Processes the raw input if present and adds the resulting
        message to the internal message buffer.

        Parameters
        ----------
        raw_input : Optional[str]
            Raw input to be processed, or None if no input is available
        """
        if raw_input is None:
            return

        pending_message = await self._raw_to_text(raw_input)

        if pending_message is not None:
            self.messages.append(pending_message)

    def formatted_latest_buffer(self) -> Optional[str]:
        """
        Format and clear the latest buffer contents.

        Retrieves the most recent message from the buffer, formats it
        with timestamp and class name, adds it to the IO provider,
        and clears the buffer.

        Returns
        -------
        Optional[str]
            Formatted string containing the latest message and metadata,
            or None if the buffer is empty

        """
        if len(self.messages) == 0:
            return None

        latest_message = self.messages[-1]

        result = f"""
INPUT: {self.descriptor_for_LLM}
// START
{latest_message.message}
// END
"""

        self.io_provider.add_input(
            self.descriptor_for_LLM, latest_message.message, latest_message.timestamp
        )
        self.messages = []

        return result
