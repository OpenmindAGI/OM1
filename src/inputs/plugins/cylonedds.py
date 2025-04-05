import asyncio
import logging
import time
from queue import Empty, Queue
from typing import List, Optional

from inputs.base import SensorConfig
from inputs.base.loop import FuserInput
from providers.cyclonedds_listener_provider import CycloneDDSListenerProvider
from providers.io_provider import IOProvider
from providers.sleep_ticker_provider import SleepTickerProvider


class CycloneDDSListener(FuserInput[str]):
    """
    CycloneDDS reader handler.

    This class manages the input stream from CycloneDDS, buffering messages
    and providing text conversion capabilities.
    """

    def __init__(self, config: SensorConfig = SensorConfig()):
        """
        Initialize the CycloneDDSListener instance.
        """
        super().__init__(config)

        # Buffer for storing the final output
        self.messages: List[str] = []

        # Set IO Provider
        self.descriptor_for_message = "Message"
        self.io_provider = IOProvider()

        # Buffer for storing messages
        self.message_buffer: Queue[str] = Queue()

        # Initialize CycloneDDSListener provider
        listen_topic = getattr(self.config, "listen_topic", None)
        if listen_topic is None:
            listen_topic = "speech"
            # Log the listen_topic being used
            logging.info(
                f"Listen topic not provided. Using default topic: {listen_topic}"
            )

        self.listener: CycloneDDSListenerProvider = CycloneDDSListenerProvider(
            message_callback=self._handle_message,
            topic=listen_topic,
        )
        self.listener.start()

        # Initialize sleep ticker provider
        self.global_sleep_ticker_provider = SleepTickerProvider()

    def _handle_message(self, message: str):
        """
        Process an incoming cyclonedds message.

        Parameters
        ----------
        message : String
        """
        try:
            self.message_buffer.put(message)
            logging.info("Heard message: %s", message)
        except Exception as e:
            logging.error(f"Error hearing: {e}")

    async def _poll(self) -> Optional[str]:
        """
        Poll for new messages in the buffer.

        Returns
        -------
        Optional[str]
            Message from the buffer if available, None otherwise
        """
        await asyncio.sleep(0.1)
        try:
            # logging.info("############Trying to read message############")
            message = self.listener.read_message()
            return message
        except Empty:
            return None

    async def _raw_to_text(self, raw_input: str) -> str:
        """
        Convert raw input to text format.

        Parameters
        ----------
        raw_input : str
            Raw input string to be converted

        Returns
        -------
        Optional[str]
            Converted text or None if conversion fails
        """
        return raw_input

    async def raw_to_text(self, raw_input: str):
        """
        Convert raw input to processed text and manage buffer.

        Parameters
        ----------
        raw_input : Optional[str]
            Raw input to be processed
        """
        pending_message = await self._raw_to_text(raw_input)
        if pending_message is None:
            if len(self.messages) != 0:
                # Skip sleep if there's already a message in the messages buffer
                self.global_sleep_ticker_provider.skip_sleep = True

        if pending_message is not None:
            if len(self.messages) == 0:
                self.messages.append(pending_message)
            else:
                self.messages[-1] = f"{self.messages[-1]} {pending_message}"

    def formatted_latest_buffer(self) -> Optional[str]:
        """
        Format and clear the latest buffer contents.

        Returns
        -------
        Optional[str]
            Formatted string of buffer contents or None if buffer is empty
        """
        if len(self.messages) == 0:
            return None

        result = f"""
{self.descriptor_for_message} INPUT
// START
{self.messages[-1]}
// END
"""
        self.io_provider.add_input(
            self.descriptor_for_message, self.messages[-1], time.time()
        )
        self.messages = []
        return result
