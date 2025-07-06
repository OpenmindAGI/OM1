import asyncio
import threading
import time
from dataclasses import dataclass
from decimal import Decimal
from queue import Empty, Queue
from typing import List, Optional

from flask import Flask, jsonify, request
from x402 import x402_payment_required

from inputs.base import SensorConfig
from inputs.base.loop import FuserInput


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


class X402Input(FuserInput[str]):
    """
    This input exposes a HTTP server that allows others to send messages to it by paying a fee.
    """

    def __init__(self, config: SensorConfig = SensorConfig()):
        """
        Initialize ASRInput instance.
        """
        super().__init__(config)

        # Set LLM description
        self.descriptor_for_LLM = getattr(self.config, "input_name", "X402 Input")

        # Buffer for storing the final output
        self.messages: List[str] = []

        # Buffer for storing messages
        self.message_buffer: Queue[str] = Queue()

        # x402 configuration
        self.fee = getattr(self.config, "fee", Decimal("0.01"))
        self.pay_to = getattr(
            self.config, "pay_to", "0xFb41AB5Bd219FbeBff7FA1febaEe2B25D19Cc5f2"
        )

        self.app = Flask(__name__)

        @self.app.route("/x402", methods=["POST"])
        @x402_payment_required(
            Decimal(self.fee),
            self.pay_to,
            description="X402 Input",
            testnet=True,
            resource_root_url="https://openmind.org",
        )
        def x402_handler():
            data = request.get_json()
            if "message" not in data:
                return jsonify({"error": "No message provided"}), 400

            message = data["message"]
            timestamp = time.time()
            self.message_buffer.put(Message(timestamp=timestamp, message=message))
            return jsonify({"status": "success", "timestamp": timestamp}), 200

        host = getattr(self.config, "host", "localhost")
        port = getattr(self.config, "port", 8765)

        self.flask_thread = threading.Thread(
            target=self._run_flask_app, args=(host, port), daemon=True
        )
        self.flask_thread.start()

    def _run_flask_app(self, host: str, port: int):
        """
        Run the Flask app in a separate thread.

        Parameters
        ----------
        host : str
            The host address for the Flask app.
        port : int
            The port number for the Flask app.
        """
        self.app.run(host=host, port=port, debug=False, use_reloader=False)

    async def _poll(self) -> Optional[str]:
        """
        Poll for new messages from the VLM service.

        Checks the message buffer for new messages with a brief delay
        to prevent excessive CPU usage.

        Returns
        -------
        Optional[str]
            The next message from the buffer if available, None otherwise
        """
        await asyncio.sleep(0.5)
        try:
            message = self.message_buffer.get_nowait()
            return message
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

        Returns
        -------
        Optional[str]
            Formatted string of buffer contents or None if buffer is empty
        """
        if len(self.messages) == 0:
            return None

        result = f"""
{self.descriptor_for_LLM} INPUT
// START
{self.messages[-1]}
// END
"""

        self.messages = []
        return result
