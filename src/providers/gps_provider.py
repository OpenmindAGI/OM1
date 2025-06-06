import logging
import re
import threading
import time
from typing import Dict, List, Optional

import serial

from providers.fabric_map_provider import RFDataRaw

from .singleton import singleton


@singleton
class GpsProvider:
    """
    GPS Provider.

    This class implements a singleton pattern to manage:
        * GPS data from serial

    Parameters
    ----------
    serial_port: str = ""
        The Serial port the Arduino is connected to
    """

    def __init__(self, serial_port: str = ""):
        """
        Robot and sensor configuration
        """

        logging.info("Booting GPS Provider")

        baudrate = 115200
        timeout = 1

        self.serial_connection = None
        try:
            self.serial_connection = serial.Serial(
                serial_port, baudrate, timeout=timeout
            )
            logging.info(f"Connected to {serial_port} at {baudrate} baud")
        except serial.SerialException as e:
            logging.error(f"Error: {e}")

        self._gps: Optional[dict] = None

        self.lat = ""
        self.lon = ""
        self.alt = 0.0
        self.sat = 0
        self.time_utc = ""

        self.yaw_mag_0_360 = 0.0
        self.yaw_mag_cardinal = ""

        self.ble_scan: List[RFDataRaw] = []

        self.running = False
        self._thread: Optional[threading.Thread] = None
        self.start()

    def magGPSProcessor(self, data):
        # Used whenever there is a connected
        # nav Arduino on serial
        try:
            if data.startswith("HDG (DEG):"):
                parts = data.split()
                if len(parts) >= 3:
                    # that's a HDG packet
                    self.yaw_mag_0_360 = float(parts[2])
                    self.yaw_mag_cardinal = self.compass_heading_to_direction(
                        self.yaw_mag_0_360
                    )
                    logging.debug(f"MAG: {self.yaw_mag_0_360}")
                else:
                    logging.warning(f"Unable to parse heading: {data}")
            elif data.startswith("YPR:"):
                yaw, pitch, roll = map(str.strip, data[4:].split(","))
                logging.debug(
                    f"Orientation is Yaw: {yaw}°, Pitch: {pitch}°, Roll: {roll}°."
                )
            elif data.startswith("GPS:"):
                try:
                    parts = data[4:].split(",")
                    lat = parts[0]
                    lon = parts[1]
                    heading = parts[3].split(":")[1]
                    alt = parts[4].split(":")[1]
                    sat = parts[5].split(":")[1]
                    self.lat = lat
                    self.lon = lon
                    self.alt = float(alt)
                    self.sat = int(sat)
                    if len(parts) >= 6:
                        time = parts[6][5:]
                        self.time_utc = time
                    logging.debug(
                        (
                            f"Current location is {lat}, {lon} at {alt}m altitude. "
                            f"GPS Heading {heading}° with {sat} satellites locked. "
                            f"The time, if available, is {self.time_utc}."
                        )
                    )
                except Exception as e:
                    logging.warning(f"Failed to parse GPS: {data} ({e})")
            elif data.startswith("BLE_TRIANG"):
                try:
                    self.ble_scan = self.parse_ble_triang_string(data)
                    logging.debug(f"BLE data {self.ble_scan}")
                except Exception as e:
                    logging.warning(f"Failed to parse BLE: {data} ({e})")
        except Exception as e:
            logging.warning(f"Error processing serial MAG/GPS/BLE input: {data} ({e})")

        self._gps = {
            "yaw_mag_0_360": self.yaw_mag_0_360,
            "yaw_mag_cardinal": self.yaw_mag_cardinal,
            "gps_lat": self.lat,
            "gps_lon": self.lon,
            "gps_alt": self.alt,
            "gps_sat": self.sat,
            "gps_time_utc": self.time_utc,
            "ble_scan": self.ble_scan,
        }

    def compass_heading_to_direction(self, degrees):
        directions = [
            "North",
            "North East",
            "East",
            "South East",
            "South",
            "South West",
            "West",
            "North West",
        ]
        index = int((degrees + 22.5) % 360 / 45)
        return directions[index]

    def parse_ble_triang_string(self, input_string):
        if not input_string.startswith("BLE_TRIANG"):
            return {}

        pattern = r"\[(\d+)\]\s+([0-9A-Fa-f:]{17})\s+(-?\d+)\s+((?:[0-9A-Fa-f]{2}:?)+)"
        matches = re.findall(pattern, input_string)

        devices: Dict[str, RFDataRaw] = {}

        timestamp = str(int(time.time()))

        for match in matches:
            index = int(match[0])
            address = match[1].replace(":", "").upper()
            rssi = int(match[2])
            packet = match[3].replace(":", "").lower()

            devices[index] = RFDataRaw(
                timestamp=timestamp, address=address, rssi=rssi, packet=packet
            )

        sorted_devices = sorted(devices.values(), key=lambda d: d.rssi, reverse=True)[
            :10
        ]

        return sorted_devices

    def start(self):
        """
        Starts the GPS Provider and processing thread
        if not already running.
        """
        if self._thread and self._thread.is_alive():
            return

        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        """
        Main loop for the GPS provider.
        """
        while self.running:
            if self.serial_connection:
                # Read a line, decode, and remove whitespace
                data = self.serial_connection.readline().decode("utf-8").strip()
                logging.debug(f"Serial GPS/MAG: {data}")
                self.magGPSProcessor(data)
            time.sleep(0.05)

    def stop(self):
        """
        Stop the GPS provider.
        """
        self.running = False
        if self._thread:
            logging.info("Stopping GPS provider")
            self._thread.join(timeout=5)

    @property
    def data(self) -> Optional[dict]:
        # """
        # Get the current robot gps data
        # """
        return self._gps
