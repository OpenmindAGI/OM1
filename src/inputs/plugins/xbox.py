import asyncio
import logging
import time
from dataclasses import dataclass
from queue import Empty, Queue
from typing import List, Optional

from inputs.base import SensorConfig
from inputs.base.loop import FuserInput
from providers.io_provider import IOProvider
from providers.xbox_provider import XboxProvider


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


class Xbox(FuserInput[str]):
    """
    Navigation input handler.

    A class that processes navigation inputs and generates text descriptions.
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

        # Initialize Navigation Provider based on .json5 config file
        self.xbox_on = False
        self.xbox = None

        xbox_timeout = 10
        xbox_attempts = 0

        while not self.xbox_on:
            logging.info(f"Waiting for Xbox Provider. Attempt {xbox_attempts}")
            self.xbox = XboxProvider(False)
            if hasattr(self.xbox, "running"):
                self.xbox_on = self.xbox.running
                logging.info(f"Xbox running?: {self.xbox_on}")
            else:
                logging.info("Waiting for Xbox")
            xbox_attempts += 1
            if xbox_attempts > xbox_timeout:
                logging.warning(
                    f"Xbox timeout after {xbox_attempts} attempts - no Xbox - DANGEROUS"
                )
                break
            time.sleep(0.5)

        self.descriptor_for_LLM = "Control inputs from an Xbox controller."

    async def _poll(self) -> Optional[str]:
        """
        Poll for new messages from the Navigation Provider.

        Checks the message buffer for new messages with a brief delay
        to prevent excessive CPU usage.

        Returns
        -------
        Optional[list]
            The next message from the buffer if available, None otherwise
        """
        await asyncio.sleep(0.1)
        try:
            return self.xbox.xbox
        except Empty:
            return None

    async def _raw_to_text(self, raw_input: str) -> Message:
        """
        Process raw input to generate a timestamped message.

        Creates a Message object from the raw input, adding
        the current timestamp.

        Parameters
        ----------
        raw_input : list
            Raw input to be processed

        Returns
        -------
        Message
            A timestamped message containing the processed input
        """
        logging.debug(f"xbox input: {raw_input}")

        # self._position = {
        #     "x": self.x,
        #     "y": self.y,
        #     "yaw_odom_0_360": self.yaw_odom_0_360,
        #     "yaw_mag_0_360": self.yaw_mag_0_360,
        #     "yaw_mag_cardinal": self.yaw_mag_cardinal,
        #     "body_height_cm": self.body_height_cm,
        #     "body_attitude": self.body_attitude
        # }

        # res = "No navigation data yet."

        # cardinal = raw_input["yaw_mag_cardinal"]
        # heading = round(raw_input["yaw_mag_0_360"])

        # if len(raw_input) >= 5:
        #     res = f"You are facing {cardinal}. Your magnetic heading is {heading} degrees."

        res = raw_input

        return Message(timestamp=time.time(), message=res)

    async def raw_to_text(self, raw_input: Optional[list]):
        """
        Convert raw input to text and update message buffer.

        Processes the raw input if present and adds the resulting
        message to the internal message buffer.

        Parameters
        ----------
        raw_input : Optional[list]
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
