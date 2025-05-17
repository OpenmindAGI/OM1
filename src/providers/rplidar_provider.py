import logging
import math
import threading
import time
from typing import Optional

import bezier
import numpy as np
import zenoh
from numpy.typing import NDArray

from zenoh_idl import sensor_msgs

from .rplidar_driver import RPDriver
from .singleton import singleton

gScan = None


def listenerScan(sample):
    global gScan
    gScan = sensor_msgs.LaserScan.deserialize(sample.payload.to_bytes())
    logging.debug(f"Zenoh Laserscan data: {gScan}")


@singleton
class RPLidarProvider:
    """
    RPLidar Provider.

    This class implements a singleton pattern to manage RPLidar data streaming.

    Parameters
    ----------
    wait: bool = False
        Whether to wait for another class to init this driver, somewhere else in the codebase
    serial_port: str = "/dev/cu.usbserial-0001"
        The name of the serial port in use by the RPLidar sensor.
    half_width_robot: float = 0.20
        The half width of the robot in m
    angles_blanked: list = []
        Regions of the scan to disregard, runs from -180 to +180 deg
    max_relevant_distance: float = 1.1
        Only consider barriers within this range, in m
    sensor_mounting_angle: float = 180.0
        The angle of the sensor zero relative to the way in which it's mounted
    """

    def __init__(
        self,
        wait: bool = False,
        serial_port: str = "/dev/cu.usbserial-0001",
        half_width_robot: float = 0.20,
        angles_blanked: list = [],
        max_relevant_distance: float = 1.1,
        sensor_mounting_angle: float = 180.0,
        URID: str = "",
        use_zenoh: bool = False,
    ):
        """
        Robot and sensor configuration
        """

        logging.info("Booting RPLidar")

        if wait:
            # no need to reinit driver
            return

        self.serial_port = serial_port
        self.half_width_robot = half_width_robot
        self.angles_blanked = angles_blanked
        self.max_relevant_distance = max_relevant_distance
        self.sensor_mounting_angle = sensor_mounting_angle
        self.URID = URID
        self.use_zenoh = use_zenoh

        self.running: bool = False
        self.lidar = None
        self.zen = None
        self.scans = None

        self._raw_scan: Optional[NDArray] = None
        self._valid_paths: Optional[list] = None
        self._lidar_string: str = None

        """
        precompute Bezier trajectories
        """
        self.curves = [
            bezier.Curve(
                np.asfortranarray([[0.0, -0.3, -0.75], [0.0, 0.5, 0.40]]), degree=2
            ),
            bezier.Curve(
                np.asfortranarray([[0.0, -0.3, -0.70], [0.0, 0.6, 0.70]]), degree=2
            ),
            bezier.Curve(
                np.asfortranarray([[0.0, -0.2, -0.60], [0.0, 0.7, 0.90]]), degree=2
            ),
            bezier.Curve(
                np.asfortranarray([[0.0, -0.1, -0.35], [0.0, 0.7, 1.03]]), degree=2
            ),
            bezier.Curve(
                np.asfortranarray([[0.0, 0.0, 0.00], [0.0, 0.5, 1.05]]), degree=2
            ),
            bezier.Curve(
                np.asfortranarray([[0.0, +0.1, +0.35], [0.0, 0.7, 1.03]]), degree=2
            ),
            bezier.Curve(
                np.asfortranarray([[0.0, +0.2, +0.60], [0.0, 0.7, 0.90]]), degree=2
            ),
            bezier.Curve(
                np.asfortranarray([[0.0, +0.3, +0.70], [0.0, 0.6, 0.70]]), degree=2
            ),
            bezier.Curve(
                np.asfortranarray([[0.0, +0.3, +0.75], [0.0, 0.5, 0.40]]), degree=2
            ),
            bezier.Curve(
                np.asfortranarray([[0.0, 0.0, 0.00], [0.0, -0.5, -1.05]]), degree=2
            ),
        ]

        self.paths = []
        self.pp = []
        self.s_vals = np.linspace(0.0, 1.0, 10)

        for curve in self.curves:
            cp = curve.evaluate_multi(self.s_vals)
            self.paths.append(cp)
            pairs = list(zip(cp[0], cp[1]))
            self.pp.append(pairs)

        # logging.info(self.paths)
        # logging.info(self.pp)

        self._thread: Optional[threading.Thread] = None

        if not self.use_zenoh:
            try:
                self.lidar = RPDriver(self.serial_port)

                info = self.lidar.get_info()
                ret = f"RPLidar Info: {info}"
                logging.info(ret)

                health = self.lidar.get_health()
                ret = f"RPLidar Health: {health}"
                logging.info(ret)

                # reset to clear buffers
                self.lidar.reset()

            except Exception as e:
                logging.error(f"Error in RPLidar provider: {e}")
        elif self.use_zenoh:
            try:
                self.zen = zenoh.open(zenoh.Config())
                logging.info(f"Zenoh move client opened {self.zen}")
                logging.info(
                    f"TurtleBot4 move listeners starting with URID: {self.URID}"
                )
                self.zen.declare_subscriber(f"{self.URID}/pi/scan", listenerScan)
            except Exception as e:
                logging.error(f"Error opening Zenoh client: {e}")

    def start(self):
        """
        Starts the RPLidar and processing thread
        if not already running.
        """
        if self._thread and self._thread.is_alive():
            return

        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _preprocess_zenoh(self, scan):

        if scan is None:
            logging.info("waiting for Zenoh Laserscan data...")
            self._raw_scan = []
            self._lidar_string = "You might be surrounded by objects and cannot safely move in any direction. DO NOT MOVE."
            self._valid_paths = []
        else:
            logging.debug(f"_preprocess_zenoh: {scan}")
            # angle_min=-3.1241390705108643, angle_max=3.1415927410125732
            angles = list(
                map(
                    lambda x: 360.0 * (x + math.pi) / (2 * math.pi),
                    np.arange(scan.angle_min, scan.angle_max, scan.angle_increment),
                )
            )

            angles_final = np.flip(angles)
            # angles now run from 360.0 to 0 degress
            data = list(zip(angles_final, scan.ranges))
            array_ready = np.array(data)
            # print(f"Array {array_ready}")
            self._process(array_ready)

    def _preprocess_serial(self, scan):
        logging.info(f"_preprocess_serial: {scan}")
        array = np.array(scan)

        # the driver sends angles in degrees between from 0 to 360
        # warning - the driver may send two or more readings per angle,
        # this can be confusing for the code
        angles = array[:, 1]

        # distances are in millimeters
        distances_mm = array[:, 2]
        distances_m = [i / 1000 for i in distances_mm]

        data = list(zip(angles, distances_m))
        array_ready = np.array(data)
        # print(f"Array {array_ready}")
        self._process(array_ready)

    def _process(self, data):

        complexes = []

        for angle, distance in data:

            d_m = distance

            # don't worry about distant objects
            if d_m > 5.0:
                continue

            # first, correctly orient the sensor zero to the robot zero
            angle = angle + self.sensor_mounting_angle
            if angle >= 360.0:
                angle = angle - 360.0
            elif angle < 0.0:
                angle = 360.0 + angle

            # then, convert to radians
            a_rad = angle * math.pi / 180.0

            v1 = d_m * math.cos(a_rad)
            v2 = d_m * math.sin(a_rad)

            # convert to x and y
            # x runs backwards to forwards, y runs left to right
            x = -1 * v2
            y = -1 * v1

            # convert the angle to -180 to + 180 range
            angle = angle - 180.0

            keep = True
            for b in self.angles_blanked:
                if angle >= b[0] and angle <= b[1]:
                    # this is a permanent reflection based on the robot
                    # disregard
                    keep = False
                    break

            # the final data ready to use for path planning
            if keep:
                complexes.append([x, y, angle, d_m])

        array = np.array(complexes)

        # sort data into strictly increasing angles to deal with sensor issues
        # the sensor sometimes reports part of the previous scan and part of the next scan
        # so you end up with multiple slightly different values for some angles at the
        # junction
        sorted_indices = array[:, 2].argsort()
        array = array[sorted_indices]

        X = array[:, 0]
        Y = array[:, 1]
        # A = array[:, 2]
        D = array[:, 3]

        """
        Determine set of possible paths
        """
        possible_paths = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])

        # all the possible conflicting points
        for x, y, d in list(zip(X, Y, D)):
            if d > self.max_relevant_distance:  # too far away - we do not care
                continue
            for apath in possible_paths:
                for point in self.pp[apath]:
                    p1 = x - point[0]
                    p2 = y - point[1]
                    dist = math.sqrt(p1 * p1 + p2 * p2)
                    if dist < self.half_width_robot:
                        # too close - this path will not work
                        path_to_remove = np.array([apath])
                        possible_paths = np.setdiff1d(possible_paths, path_to_remove)
                        break  # no need to keep checking this path - we know this path is bad

        turn_left = []
        advance = []
        turn_right = []
        retreat = []

        for p in possible_paths:
            if p < 4:
                turn_left.append(p)
            elif p == 4:
                advance.append(p)
            elif p < 9:
                turn_right.append(p)
            elif p == 9:
                retreat.append(p)

        return_string = "You are surrounded by objects and cannot safely move in any direction. DO NOT MOVE."

        if len(possible_paths) > 0:
            return_string = "The safe movement choices are: "
            if self.use_zenoh:  # i.e. you are controlling a TurtleBot4
                return_string += "You can turn left. You can turn right. "
                if len(advance) > 0:
                    return_string += "You can move forwards. "
            else:
                if len(turn_left) > 0:
                    return_string += "You can turn left. "
                if len(advance) > 0:
                    return_string += "You can move forwards. "
                if len(turn_right) > 0:
                    return_string += "You can turn right. "
                if len(retreat) > 0:
                    return_string += "You can move back. "

        self._raw_scan = array
        self._lidar_string = return_string
        self._valid_paths = possible_paths.tolist()

        logging.debug(
            f"RPLidar Provider string: {self._lidar_string}\nValid paths: {self._valid_paths}"
        )

    def _run(self):
        """
        Main loop for the RPLidar provider.

        Continuously processes RPLidar data and send them
        to the inputs and actions, as needed.
        """
        while self.running:
            if self.use_zenoh:
                global gScan
                logging.debug(f"Zenoh: {gScan}")
                self._preprocess_zenoh(gScan)
                time.sleep(0.1)
            else:
                # we are using serial
                try:
                    for i, scan in enumerate(
                        self.lidar.iter_scans(
                            scan_type="express", max_buf_meas=3000, min_len=5
                        )
                    ):
                        self._preprocess_serial(scan)
                    # not sure about the level of this?
                    time.sleep(0.1)
                except Exception as e:
                    logging.error(f"Error in Serial RPLidar provider: {e}")

    def stop(self):
        """
        Stop the RPLidar provider.
        """
        self.running = False
        if self._thread:
            logging.info("Stopping RPLidar provider")
            if not self.use_zenoh:
                self.lidar.stop()
                self.lidar.disconnect()
                time.sleep(0.5)
            self._thread.join(timeout=5)

    @property
    def valid_paths(self) -> Optional[list]:
        """
        Get the currently valid paths.

        Returns
        -------
        Optional[list]
            The currently valid paths as a list, or None if not
            available. The list contains 0 to 10 entries,
            corresponding to possible paths - for example: [0,3,4,5]
        """
        return self._valid_paths

    @property
    def raw_scan(self) -> Optional[NDArray]:
        """
        Get the latest raw scan data.

        Returns
        -------
        Optional[NDArray]
            The latest raw scan result as a NumPy array, or None if not
            available.
        """
        return self._raw_scan

    @property
    def lidar_string(self) -> str:
        """
        Get the latest natural language assessment of possible paths.

        Returns
        -------
        str
            A natural language summary of possible motion paths
        """
        return self._lidar_string
