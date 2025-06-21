import datetime
import logging
import re
import threading
import time
from typing import Optional

import serial
from pynmeagps import NMEAReader

from .singleton import singleton


@singleton
class RtkProvider:
    """
    RTK Provider.

    This class implements a singleton pattern to manage:
        * RTK data from serial

    Parameters
    ----------
    serial_port: str = ""
    """

    def __init__(self, serial_port: str = ""):
        """
        Robot and sensor configuration
        """

        logging.info("Booting RTK Provider")

        baudrate = 115200
        timeout = 0.2  # seconds

        self.serial_connection = None
        try:
            self.serial_connection = serial.Serial(
                serial_port, baudrate, timeout=timeout
            )
            self.serial_connection.reset_input_buffer()
            logging.info(f"Connected to {serial_port} at {baudrate} baud")
        except serial.SerialException as e:
            logging.error(f"Error: {e}")

        self._rtk: Optional[dict] = None

        self.lat = 0.0
        self.lon = 0.0
        self.alt = 0.0
        self.sat = 0
        self.qua = 0
        self.time_utc = ""

        self.running = False
        self._thread: Optional[threading.Thread] = None
        self.start()

    def get_latest_gngga_message(self, nmea_data):

        pattern = re.compile(
            r"(\$GNGGA,(?P<time>\d{6}(?:\.\d+)?),[^*]*\*[0-9A-Fa-f]{2})", re.MULTILINE
        )

        gngga_entries = []

        matches = pattern.finditer(nmea_data)

        for match in matches:
            # logging.info(f"matches: {match}")
            full_msg = match.group(1)
            time_str = match.group("time")
            try:
                time_val = float(time_str)
                gngga_entries.append((time_val, full_msg))
            except ValueError:
                continue  # Skip if time field is malformed

        # Sort by time and return the latest message
        most_recent = max(gngga_entries, key=lambda x: x[0])

        # "most_recent" is a time and the message,
        # the [1] just returns the message
        return most_recent[1]

    def magRTKProcessor(self, msg):

        try:
            logging.debug(f"RTK:{msg}")

            # NMEA-GN-GGA
            # Description:
            # Standard NMEA: Global positioning system fix data. This message contains time, date,
            # position (in LLH coordinates), fix quality, number of satellites, and horizontal dilution of
            # precision (HDOP) data provided by the selected source.

            if msg.msgID == "GGA":
                try:
                    # round to 1 cm localisation in x,y, and 1 cm in z
                    logging.debug(f"RTK GGA:{msg}")

                    self.lat = round(float(msg.lat), 7)
                    self.lon = round(float(msg.lon), 7)
                    self.alt = round(float(msg.alt), 2)

                    self.sat = int(msg.numSV)
                    self.qua = int(msg.quality)

                    ms = msg.time.strftime("%f")[:3]
                    time_with_ms = msg.time.strftime("%H:%M:%S") + ":" + ms

                    timestamp = time.time()
                    datetime_utc_str = datetime.datetime.fromtimestamp(
                        timestamp, datetime.UTC
                    ).strftime("%Y:%m:%d")

                    self.time_utc = datetime_utc_str + ":" + time_with_ms
                    logging.info(
                        (
                            f"RTK:{self.lat},{self.lon},ALT:{self.alt},"
                            f"QUA:{self.qua},SAT:{self.sat},TIME:{self.time_utc}"
                        )
                    )
                except Exception as e:
                    logging.warning(f"Failed to parse GGA message: {msg} ({e})")
        except Exception as e:
            logging.warning(f"Error processing serial RTK input: {msg} ({e})")

        self._rtk = {
            "rtk_lat": self.lat,
            "rtk_lon": self.lon,
            "rtk_alt": self.alt,
            "rtk_sat": self.sat,
            "rtk_qua": self.qua,
            "rtk_time_utc": self.time_utc,
        }

    def start(self):
        """
        Starts the RTK Provider and processing thread
        if not already running.
        """
        if self._thread and self._thread.is_alive():
            return

        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        """
        Main loop for the RTK provider.
        """
        while self.running:

            if self.serial_connection:  # and self.nmr:
                try:
                    # read 1000 bytes and find the GNGAA messages
                    data = self.serial_connection.read(size=1000)
                    data = data.decode("utf-8", errors="ignore")
                    ### logging.info(f"RTK data: {data}")
                    latest_GNGGA = self.get_latest_gngga_message(data)
                    parsed_nema = NMEAReader.parse(latest_GNGGA)
                    ### logging.info(f"GNGGA message: {parsed_nema}")
                    self.magRTKProcessor(parsed_nema)
                except Exception:
                    pass

            time.sleep(0.5)

    def stop(self):
        """
        Stop the RTK provider.
        """
        self.running = False
        if self._thread:
            logging.info("Stopping RTK provider")
            self._thread.join(timeout=5)

    @property
    def data(self) -> Optional[dict]:
        """
        Get the current robot RTK data.

        Returns
        -------
        Optional[dict]
            Dictionary containing RTK position data or None if not available
        """
        return self._rtk
