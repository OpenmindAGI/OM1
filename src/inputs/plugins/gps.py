import asyncio
import logging
import time
from dataclasses import dataclass
from queue import Empty
from typing import Optional

from inputs.base import SensorConfig
from inputs.base.loop import FuserInput
from providers.gps_provider import GpsProvider
from providers.io_provider import IOProvider

# Map of abbreviated compass directions to full words
CARDINAL_MAP = {
    "N": "North",
    "NNE": "North-Northeast",
    "NE": "Northeast",
    "ENE": "East-Northeast",
    "E": "East",
    "ESE": "East-Southeast",
    "SE": "Southeast",
    "SSE": "South-Southeast",
    "S": "South",
    "SSW": "South-Southwest",
    "SW": "Southwest",
    "WSW": "West-Southwest",
    "W": "West",
    "WNW": "West-Northwest",
    "NW": "Northwest",
    "NNW": "North-Northwest",
}


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


class Gps(FuserInput[str]):
    """
    Reads GPS and Magnetometer data from GPS provider.
    """

    def __init__(self, config: SensorConfig = SensorConfig()):
        super().__init__(config)

        port = getattr(config, "serial_port", None)
        self.silent = getattr(config, "silent", False)

        self.gps = GpsProvider(serial_port=port)
        self.io_provider = IOProvider()
        self.messages: list[Message] = []
        self.descriptor_for_LLM = "Location and Orientation"

    async def _poll(self) -> Optional[dict]:
        """
        Poll for new messages from the GPS Provider.

        Checks the message buffer for new messages with a brief delay
        to prevent excessive CPU usage.

        Returns
        -------
        Optional[dict]
            The next message from the buffer if available, None otherwise
        """
        await asyncio.sleep(0.5)

        if self.silent:
            return None

        try:
            return self.gps.data
        except Empty:
            return None

    async def _raw_to_text(self, raw_input: dict) -> Optional[Message]:
        """
        Process raw input to generate a timestamped message.

        Creates a Message object from the raw input, adding
        the current timestamp.

        Parameters
        ----------
        raw_input : dict
            Raw input to be processed

        Returns
        -------
        Message
            A timestamped message containing the processed input
        """
        logging.debug(f"gps: {raw_input}")

        d = raw_input
        if d:
            logging.debug(f"GPS Provider: {d}")
            lat = d["gps_lat"]
            lon = d["gps_lon"]
            alt = d["gps_alt"]
            sats = d["gps_sats"]
            if sats > 0:
                msg = f"Current location is {lat}, {lon} at {alt}m altitude."
                return Message(timestamp=time.time(), message=msg)
            else:
                return None
        else:
            return None

    async def raw_to_text(self, raw_input: dict):
        """
        Update message buffer.
        """
        pending_message = await self._raw_to_text(raw_input)

        if pending_message is not None:
            self.messages.append(pending_message)

    def formatted_latest_buffer(self) -> Optional[str]:
        """
        Format and clear the latest buffer contents.

        Formats the most recent message with timestamp and class name,
        adds it to the IO provider, then clears the buffer.

        Returns
        -------
        Optional[str]
            Formatted string of buffer contents or None if buffer is empty
        """
        if len(self.messages) == 0:
            return None

        latest_message = self.messages[-1]

        result = (
            f"\nINPUT: {self.descriptor_for_LLM}\n// START\n"
            f"{latest_message.message}\n// END\n"
        )

        self.io_provider.add_input(
            self.__class__.__name__, latest_message.message, latest_message.timestamp
        )
        self.messages = []

        return result
