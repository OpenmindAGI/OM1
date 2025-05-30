import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime

import requests

from .singleton import singleton


@dataclass
class FabricData:
    """
    Data class to represent a data payload from a machine to FABRIC.
    """

    machine_id: str
    gps_time_utc: str
    gps_lat: str
    gps_lon: str
    gps_alt: float
    mag: float
    update_time_local: float
    odom_x: float
    odom_y: float
    yaw_odom_0_360: float
    yaw_odom_m180_p180: float
    rf_data: list

    def to_dict(self) -> dict:
        """
        Convert the FabricData object to a dictionary.

        Returns
        -------
        dict
            Dictionary representation of the FabricData object.
        """
        return {
            "machine_id": self.machine_id,
            "gps_time_utc": self.gps_time_utc,
            "gps_lat": self.gps_lat,
            "gps_lon": self.gps_lon,
            "gps_alt": self.gps_alt,
            "mag": self.mag,
            "update_time_local": self.update_time_local,
            "odom_x": self.odom_x,
            "odom_y": self.odom_y,
            "yaw_odom_0_360": self.yaw_odom_0_360,
            "yaw_odom_m180_p180": self.yaw_odom_m180_p180,
            "rf_data": self.rf_data,
        }


@singleton
class FabricDataSubmitter:
    """
    Allows a machine to locally log mapping data and submit data to FABRIC.
    """

    def __init__(
        self,
        api_key: str = None,
        base_url: str = "https://api.openmind.org/api/core/fabric/submit",
        write_to_local_file: bool = False,
    ):
        """
        Initialize the FabricDataSubmitter.

        Parameters
        ----------
        api_key : str
            API key for authentication. Default is None.
        base_url : str
            Base URL for the teleops status API. Default is
            "https://api.openmind.org/api/core/fabric/submit".
        """
        self.api_key = api_key
        self.base_url = base_url
        self.write_to_local_file = write_to_local_file
        self.executor = ThreadPoolExecutor(max_workers=1)

    def write_dict_to_file(
        self, data: dict, base_filename: str, max_file_size_bytes: int = 1024 * 1024
    ):
        """
        Writes a dictionary to a file in JSON lines format. If the file exceeds max_file_size_bytes,
        creates a new file with a timestamp.

        Parameters:
        - data: Dictionary to write
        - base_filename: Base name for the file (e.g., 'log.jsonl')
        - max_file_size_bytes: Maximum allowed size before rolling over to a new file
        """
        # logging.info(f"write_dict_to_file: {data}")

        if not isinstance(data, dict):
            raise ValueError("Provided data must be a dictionary.")

        def get_new_filename():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name, ext = os.path.splitext(base_filename)
            return f"{name}_{timestamp}{ext}"

        # Use the base filename or roll over if too large
        if (
            os.path.exists(base_filename)
            and os.path.getsize(base_filename) > max_file_size_bytes
        ):
            base_filename = get_new_filename()
            logging.info(f"new file name: {base_filename}")

        with open(base_filename, "a", encoding="utf-8") as f:
            json_line = json.dumps(data)
            f.write(json_line + "\n")

        return base_filename

    def _share_data_worker(self, data: FabricData):
        """
        Worker function to share data from the machine.
        This function runs in a separate thread to avoid blocking the main thread.

        Parameters
        ----------
        data : FabricData
            The data to be shared.
        """

        # logging.info(f"prepare data: {data}")
        try:
            json_dict = data.to_dict()
        except Exception as e:
            logging.error(f"Error converting to dict: {str(e)}")

        if self.write_to_local_file:
            name_used = self.write_dict_to_file(
                json_dict, "fabric_log.jsonl", max_file_size_bytes=1024 * 512
            )
            logging.info(f"FDS wrote to this file: {name_used}")

        if self.api_key is None or self.api_key == "":
            logging.error("API key is missing. Cannot share data to FABRIC cloud.")
            return

        try:
            request = requests.post(
                self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=json_dict,
            )

            if request.status_code == 200:
                logging.debug(f"Data shared successfully: {request.json()}")
            else:
                logging.error(
                    f"Failed to share data: {request.status_code} - {request.text}"
                )
        except Exception as e:
            logging.error(f"Error sharing data: {str(e)}")

    def share_data(self, data: FabricData):
        """
        Share mapping data.
        This function submits mapping data collected by a machine to a thread pool executor
        to run in a separate thread.

        Parameters
        ----------
        data : FabricData
            A mapping data payload to submit.
        """
        # logging.info(f"data: {data}")
        self.executor.submit(self._share_data_worker, data)
