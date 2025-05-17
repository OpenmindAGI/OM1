import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

import serial

from inputs.base import SensorConfig
from inputs.base.loop import FuserInput
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


class SerialReader(FuserInput[str]):
    """
    Reads GPS and Magnetometer data from serial port.
    Parses lines like:
    - GPS:37.7749N,-122.4194W,KN:0.12,HEAD:84.1,ALT:30.5,SAT:7
    - YPR: 134.57, -3.20, 1.02
    - HDG (DEG): 225.0 SW NTC_HDG: 221.3
    """

    def __init__(self, config: SensorConfig = SensorConfig()):
        super().__init__(config)

        port = getattr(config, "port", None)
        baudrate = 115200
        timeout = 1

        self.ser = None
        try:
            self.ser = serial.Serial(port, baudrate, timeout=timeout)
            logging.info(f"Connected to {port} at {baudrate} baud")
        except serial.SerialException as e:
            logging.error(f"Error: {e}")

        self.io_provider = IOProvider()
        self.messages: list[Message] = []
        self.descriptor_for_LLM = "Location and Orientation"

    async def _poll(self) -> str | None:
        """
        Poll for serial data.

        Returns
        -------
        str
            message on serial bus
        """

        await asyncio.sleep(0.5)
        if not self.ser:
            return None

        data = self.ser.readline().decode("utf-8").strip()
        # Read a line, decode, and remove whitespace

        if data:
            logging.info(f"Serial: {data}")
            return data
        return None

    async def _raw_to_text(self, raw_input: str) -> Message:
        msg = "Unrecognized data"

        try:
            if raw_input.startswith("HDG (DEG):"):
                parts = raw_input.split()
                if len(parts) >= 4:
                    cardinal_abbr = parts[3]
                    direction = CARDINAL_MAP.get(cardinal_abbr, cardinal_abbr)
                    msg = f"You are facing {direction}."
                else:
                    msg = f"Unable to parse heading: {raw_input}"

            elif raw_input.startswith("YPR:"):
                yaw, pitch, roll = map(str.strip, raw_input[4:].split(","))
                msg = f"Orientation is Yaw: {yaw}°, Pitch: {pitch}°, Roll: {roll}°."

            elif raw_input.startswith("GPS:"):
                try:
                    parts = raw_input[4:].split(",")
                    lat = parts[0]
                    lon = parts[1]
                    heading = parts[3].split(":")[1]
                    alt = parts[4].split(":")[1]
                    sats = parts[5].split(":")[1]
                    msg = (
                        f"Current location is {lat}, {lon} at {alt} meters altitude, "
                        f"heading {heading}°, with {sats} satellites locked."
                    )
                except Exception as e:
                    msg = f"Failed to parse GPS: {raw_input} ({e})"

        except Exception as e:
            msg = f"Error processing input: {raw_input} ({e})"

        return Message(timestamp=time.time(), message=msg)

    async def raw_to_text(self, raw_input: str):
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

        result = f"""
INPUT: {self.descriptor_for_LLM} 
// START
{latest_message.message}
// END
"""

        self.io_provider.add_input(
            self.__class__.__name__, latest_message.message, latest_message.timestamp
        )
        self.messages = []

        return result
