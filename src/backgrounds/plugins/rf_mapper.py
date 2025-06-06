import asyncio
import logging
import threading
import time
from typing import Dict, List

from bleak import AdvertisementData, BleakScanner

from backgrounds.base import Background, BackgroundConfig
from providers.fabric_map_provider import (
    FabricData,
    FabricDataSubmitter,
    RFData,
    RFDataRaw,
)
from providers.gps_provider import GpsProvider
from providers.odom_provider import OdomProvider
from providers.rtk_provider import RtkProvider


class RFmapper(Background):
    """
    Example background implementation that runs indefinitely.
    """

    def __init__(self, config: BackgroundConfig):
        """
        Initialize the RFmapper with configuration.

        Parameters
        ----------
        config : BackgroundConfig
            Configuration object for the background.
        """
        super().__init__(config)
        self.name = getattr(config, "name", "RFmapper")
        self.api_key = getattr(config, "api_key", None)
        self.URID = getattr(config, "URID", None)
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._scan_task)
        self.running = False
        self.scan_results: List[RFData] = []

        self.x = 0.0
        self.y = 0.0
        self.yaw_odom_0_360 = 0.0
        self.yaw_odom_m180_p180 = 0.0

        self.gps_time_utc = ""
        self.gps_lat = 0.0
        self.gps_lon = 0.0
        self.gps_alt = 0.0
        self.yaw_mag_0_360 = 0.0
        self.ble_scan: List[RFDataRaw] = []

        self.rtk_time_utc = ""
        self.rtk_lat = 0.0
        self.rtk_lon = 0.0
        self.rtk_alt = 0.0
        self.rtk_qua = 0

        self.gps = GpsProvider()
        self.gps_on = self.gps.running
        logging.info(f"Mapper Gps Provider: {self.gps}")

        self.rtk = RtkProvider()
        self.rtk_on = self.rtk.running
        logging.info(f"Mapper Rtk Provider: {self.rtk}")

        self.odom = OdomProvider()
        logging.info(f"Mapper Odom Provider: {self.odom}")

        self.fds = FabricDataSubmitter(api_key=self.api_key, write_to_local_file=True)

        self.start()

    async def scan_once(self):

        seen_devices: Dict[str, RFData] = {}

        def detection_callback(device, advdata: AdvertisementData):
            logging.debug(f"adv...{advdata}")

            # AdvertisementData(
            # local_name: Optional[str],
            # manufacturer_data: Dict[int, bytes],
            # service_data: Dict[str, bytes],
            # service_uuids: List[str],
            # tx_power: Optional[int],
            # rssi: int, platform_data: Tuple)

            service_uuid = ""
            mfgkey = ""
            mfgval = ""
            if advdata.manufacturer_data:
                for key, value in advdata.manufacturer_data.items():
                    mfgkey = hex(key).upper()
                    mfgval = value.hex().upper()
                    break
            if advdata.service_uuids:
                service_uuid = advdata.service_uuids[0]

            seen_devices[device.address] = RFData(
                timestamp=time.time(),
                address=device.address,
                name=device.name if device.name else "Unknown",
                rssi=advdata.rssi,
                service_uuid=service_uuid,
                mfgkey=mfgkey,
                mfgval=mfgval,
            )

        scanner = BleakScanner(detection_callback)
        await scanner.start()
        await asyncio.sleep(1.0)
        await scanner.stop()

        # Get the top 10 devices with the strongest RSSI
        sorted_devices = sorted(
            seen_devices.values(), key=lambda d: d.rssi, reverse=True
        )[:10]
        # logging.info(f"Scan...{sorted_devices}")
        return sorted_devices

    def _scan_task(self):
        asyncio.set_event_loop(self.loop)
        logging.info("Starting RF scan thread...")
        self.running = True
        while self.running:
            self.scan_results = self.loop.run_until_complete(self.scan_once())
            time.sleep(1)

    def start(self):
        self.thread.start()

    def stop(self):
        self.running = False
        time.sleep(1)
        self.thread.join()

    def run(self) -> None:
        """
        Run the background process.
        This method will run indefinitely, simulating a long-running task.
        """
        try:
            while self.running:
                # logging.info(f"RF mapper: {self.scan_results}")

                if hasattr(self.gps, "running"):
                    if self.scan_results and self.gps.data:
                        logging.debug(
                            f"RF scan results available, processing... {self.scan_results}"
                        )
                        try:
                            g = self.gps.data
                            logging.debug(f"GPS data: {g}")
                            if g:
                                self.gps_time_utc = g["gps_time_utc"]

                                lat = g["gps_lat"]
                                if lat[-1] == "N":
                                    self.gps_lat = float(lat[:-1])
                                else:
                                    self.gps_lat = -1.0 * float(lat[:-1])

                                lon = g["gps_lon"]
                                if lon[-1] == "E":
                                    self.gps_lon = float(lon[:-1])
                                else:
                                    self.gps_lon = -1.0 * float(lon[:-1])

                                self.gps_alt = g["gps_alt"]
                                self.yaw_mag_0_360 = g["yaw_mag_0_360"]
                                self.ble_scan = g["ble_scan"]
                                logging.debug(f"RF scan results {self.ble_scan}")
                        except Exception as e:
                            logging.error(f"Error parsing GPS: {e}")

                        try:
                            o = self.odom
                            logging.debug(f"Odom data: {o}")
                            if o:
                                self.x = o.x
                                self.y = o.y
                                self.yaw_odom_0_360 = o.yaw_odom_0_360
                                self.yaw_odom_m180_p180 = o.yaw_odom_m180_p180
                        except Exception as e:
                            logging.error(f"Error parsing Odom: {e}")

                        if hasattr(self.rtk, "running"):
                            try:
                                r = self.rtk.data
                                logging.debug(f"RTK data: {r}")
                                if r:
                                    self.rtk_time_utc = r["rtk_time_utc"]
                                    self.rtk_lat = r["rtk_lat"]
                                    self.rtk_lon = r["rtk_lon"]
                                    self.rtk_alt = r["rtk_alt"]
                                    self.rtk_qua = r["rtk_qua"]
                            except Exception as e:
                                logging.error(f"Error parsing RTK: {e}")

                        try:
                            self.fds.share_data(
                                FabricData(
                                    machine_id=self.URID,
                                    gps_time_utc=self.gps_time_utc,
                                    gps_lat=self.gps_lat,
                                    gps_lon=self.gps_lon,
                                    gps_alt=self.gps_alt,
                                    rtk_time_utc=self.rtk_time_utc,
                                    rtk_lat=self.rtk_lat,
                                    rtk_lon=self.rtk_lon,
                                    rtk_alt=self.rtk_alt,
                                    rtk_qua=self.rtk_qua,
                                    mag=self.yaw_mag_0_360,
                                    update_time_local=time.time(),
                                    odom_x=self.x,
                                    odom_y=self.y,
                                    yaw_odom_0_360=self.yaw_odom_0_360,
                                    yaw_odom_m180_p180=self.yaw_odom_m180_p180,
                                    rf_data=self.scan_results,
                                    rf_data_raw=self.ble_scan,
                                )
                            )
                        except Exception as e:
                            logging.error(f"Error sharing to Fabric: {e}")

                        self.scan_results = []

                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("Stopping RF scanner...")
            self.stop()
