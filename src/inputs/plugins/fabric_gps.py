import asyncio
import logging
import time
from dataclasses import dataclass
from queue import Queue
from typing import List, Optional

import requests

from inputs.base import SensorConfig
from inputs.base.loop import FuserInput
from providers.io_provider import IOProvider


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


class FabricGPSInput(FuserInput[str]):
    """
    This input share GPS coordinates with the Fabric network and
    retrieves the closest node to the current position.
    """

    def __init__(self, config: SensorConfig = SensorConfig()):
        """
        Initialize FabricGPSInput instance.
        """
        super().__init__(config)

        self.descriptor_for_LLM = "Fabric Network GPS Input"

        # Buffer for storing the final output
        self.messages: List[str] = []

        # Set IO Provider
        self.io_provider = IOProvider()

        # Buffer for storing messages
        self.message_buffer: Queue[str] = Queue()

        # Fabric endpoint confguration
        self.fabric_endpoint = getattr(
            self.config, "fabric_endpoint", "http://localhost:8545"
        )

    async def _poll(self) -> Optional[str]:
        """
        Share GPS coordinates with the Fabric network and retrieve the closest node.

        Returns
        -------
        Optional[str]
            The closest node to the current position.
        """
        await asyncio.sleep(0.5)

        # Find the closest node
        try:
            find_closest_node_response = requests.post(
                f"{self.fabric_endpoint}",
                json={
                    "method": "omp2p_findClosestPeer",
                    "params": [{"latitude": 0, "longitude": 0}],
                    "id": 1,
                    "jsonrpc": "2.0",
                },
                headers={"Content-Type": "application/json"},
            )
            response = find_closest_node_response.json()
            logging.info(f"Find closest node response: {response}")
            if "result" in response and response["result"] and len(response["result"]) > 0:
                logging.info(f"Found closest node: {response['result']}")
                # Access the first result
                peer_info = response["result"][0]["peer"]
                lat = peer_info["latitude"]
                lon = peer_info["longitude"]

                # Save for others
                self.io_provider.add_dynamic_variable("closest_peer_lat", lat)
                self.io_provider.add_dynamic_variable("closest_peer_lon", lon)

                # Optionally enqueue a human‑readable message
                self.message_buffer.put(f"Closest peer at {lat:.5f}, {lon:.5f}")
            else:
                logging.info("No closest node found.")
                return None
        except Exception as e:
            logging.error(f"Error while finding the closest node: {e}")
            return None

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
        self.io_provider.add_input(
            self.descriptor_for_LLM, self.messages[-1], time.time()
        )
        self.messages = []
        return result
