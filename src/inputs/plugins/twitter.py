import json
import asyncio
from queue import Queue, Empty
import logging
from typing import Dict, Optional, List

from providers.asr_provider import ASRProvider
from providers.sleep_ticker_provider import SleepTickerProvider

from inputs.base.loop import LoopInput

class TwitterInput(LoopInput[str]):
    """Twitt data puller input handler.

    This class manages the input stream from an Twitter data aggregator service, 
    uffering messages.

    Attributes
    ----------
    message_buffer : Queue[str]
        FIFO queue for storing incoming Twitter messages
    twp : TwitterProvider
        Provider for Twitter websocket connection
    global_sleep_ticker_provider : SleepTickerProvider
        Provider for managing sleep ticks
    buffer : List[str]
        Internal buffer for storing processed twitter data
    """
    def __init__(self):
        super().__init__()

        # Buffer for storing the final output
        self.buffer: List[str] = []

        # Buffer for storing messages
        self.message_buffer: Queue[str] = Queue()

        # Initialize ASR provider
        self.twp: TwitterProvider = ASRProvider(ws_url="wss://api-twitter.openmind.org")
        self.twp.start()
        self.twp.register_message_callback(self._handle_twp_message)

        # Initialize sleep ticker provider
        self.global_sleep_ticker_provider = SleepTickerProvider()

    def _handle_twitter_message(self, raw_message: str):
        """
        Process incoming Twitter payloads.

        Parameters
        ----------
        raw_message : str
            Raw message received from Twitter service
        """
        try:
            json_message: Dict = json.loads(raw_message)
            if "twitter_reply" in json_message:
                twitter_reply = json_message["twitter_reply"]
                self.message_buffer.put(twitter_reply)
                logging.info("Detected Twitter message: %s", twitter_reply)
        except json.JSONDecodeError:
            pass

    async def _poll(self) -> Optional[str]:
        """
        Poll for new messages in the buffer.

        Returns
        -------
        Optional[str]
            Message from the buffer if available, None otherwise
        """
        await asyncio.sleep(0.5)
        try:
            message = self.message_buffer.get_nowait()
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

    async def raw_to_text(self, raw_input):
        """
        Convert raw input to processed text and manage buffer.

        Parameters
        ----------
        raw_input : Optional[str]
            Raw input to be processed
        """
        text = await self._raw_to_text(raw_input)
        if text is None:
            if len(self.buffer) == 0:
                return None
            else:
                # Skip sleep if there's already a message in the buffer
                self.global_sleep_ticker_provider.skip_sleep = True

        if text is not None:
            if len(self.buffer) == 0:
                self.buffer.append(text)
            else:
                self.buffer[-1] = f"{self.buffer[-1]} {text}"

    def formatted_latest_buffer(self) -> Optional[str]:
        """
        Format and clear the latest buffer contents.

        Returns
        -------
        Optional[str]
            Formatted string of buffer contents or None if buffer is empty
        """
        if len(self.buffer) == 0:
            return None

        result = f"""
{self.__class__.__name__} INPUT
// START
{self.buffer[-1]}
// END
"""
        self.buffer = []
        return result
