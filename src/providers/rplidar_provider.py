import logging
import math
import threading
import time
from typing import Dict, List, Optional

import bezier
import numpy as np
import zenoh
from numpy.typing import NDArray

from zenoh_idl import sensor_msgs
from zenoh_idl.sensor_msgs import LaserScan

from .rplidar_driver import RPDriver
from .singleton import singleton


@singleton
class RPLidarProvider:
    """
    RPLidar Provider.

    This class implements a singleton pattern to manage RPLidar data streaming.

    Parameters
    ----------
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
        serial_port: str = "/dev/cu.usbserial-0001",
        half_width_robot: float = 0.20,
        angles_blanked: list = [],
        max_relevant_distance: float = 1.1,
        sensor_mounting_angle: float = 180.0,
        URID: str = "",
        use_zenoh: bool = False,
        simple_paths: bool = False,
    ):
        """
        Robot and sensor configuration
        """

        logging.info("Booting RPLidar")

        self.serial_port = serial_port
        self.half_width_robot = half_width_robot
        self.angles_blanked = angles_blanked
        self.max_relevant_distance = max_relevant_distance
        self.sensor_mounting_angle = sensor_mounting_angle
        self.URID = URID
        self.use_zenoh = use_zenoh
        self.simple_paths = simple_paths

        self.running: bool = False
        self.lidar = None
        self.zen = None
        self.scans = None

        self._raw_scan: Optional[NDArray] = None
        self._valid_paths: Optional[list] = None
        self._lidar_string: str = None

        self.angles = None
        self.angles_final = None

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

        self.turn_left: List[int] = []
        self.turn_right: List[int] = []
        self.advance: bool = False
        self.retreat: bool = False

        self._thread: Optional[threading.Thread] = None

        if not self.use_zenoh:
            try:
                self.lidar = RPDriver(self.serial_port)

                info = self.lidar.get_info()
                ret = f"RPLidar Info: {info}"

                logging.info(ret)

                health = self.lidar.get_health()
                ret = f"RPLidar Health: {health[0]}"
                logging.info(ret)

                if health[0] == "Good":
                    logging.info(ret)
                else:
                    logging.info(f"there is a problem with the LIDAR: {ret}")

                # reset to clear buffers
                self.lidar.reset()

                time.sleep(0.5)

            except Exception as e:
                logging.error(f"Error in RPLidar provider: {e}")

        elif self.use_zenoh:
            logging.info("Connecting to the RPLIDAR via Zenoh")
            try:
                self.zen = zenoh.open(zenoh.Config())
                logging.info(f"Zenoh move client opened {self.zen}")
                logging.info(
                    f"TurtleBot4 RPLIDAR listener starting with URID: {self.URID}"
                )
                self.zen.declare_subscriber(f"{self.URID}/pi/scan", self.listen_scan)
            except Exception as e:
                logging.error(f"Error opening Zenoh client: {e}")

    def listen_scan(self, data: zenoh.Sample):
        """
        Zenoh scan handler.

        Parameters
        ----------
        data : zenoh.Sample
            The Zenoh sample containing the scan data.
        """
        self.scans = sensor_msgs.LaserScan.deserialize(data.payload.to_bytes())
        logging.debug(f"Zenoh Laserscan data: {self.scans}")

        self._preprocess_zenoh(self.scans)

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

    def _preprocess_zenoh(self, scan: Optional[LaserScan]):
        """
        Preprocess Zenoh LaserScan data.

        Parameters
        ----------
        scan : Optional[LaserScan]
            The Zenoh LaserScan data to preprocess.
            If None, it indicates no data is available.
        """
        if scan is None:
            logging.info("Waiting for Zenoh Laserscan data...")
            self._raw_scan = []
            self._lidar_string = "You might be surrounded by objects and cannot safely move in any direction. DO NOT MOVE."
            self._valid_paths = []
        else:
            # logging.debug(f"_preprocess_zenoh: {scan}")
            # angle_min=-3.1241390705108643, angle_max=3.1415927410125732

            if not self.angles:
                self.angles = list(
                    map(
                        lambda x: 360.0 * (x + math.pi) / (2 * math.pi),
                        np.arange(scan.angle_min, scan.angle_max, scan.angle_increment),
                    )
                )
                self.angles_final = np.flip(self.angles)

            # angles now run from 360.0 to 0 degress
            data = list(zip(self.angles_final, scan.ranges))
            array_ready = np.array(data)
            self._process(array_ready)

    def _preprocess_serial(self, scan: LaserScan):
        """
        Preprocess serial LaserScan data.

        Parameters
        ----------
        scan : LaserScan
            The serial LaserScan data to preprocess.
            This is expected to be a 2D array with angles and distances.
        """
        logging.debug(f"_preprocess_serial: {scan}")
        array = np.array(scan)

        # logging.info(f"_preprocess_serial: {array.ndim}")

        # the driver sends angles in degrees between from 0 to 360
        # warning - the driver may send two or more readings per angle,
        # this can be confusing for the code
        angles = array[:, 0]

        # logging.info(f"_preprocess_serial: {angles}")

        # distances are in millimeters
        distances_m = array[:, 1] / 1000

        data = list(zip(angles, distances_m))

        # logging.info(f"_preprocess_serial: {data}")
        array_ready = np.array(data)
        # print(f"Array {array_ready}")
        self._process(array_ready)

    def _process(self, data: NDArray):
        """
        Process the RPLidar data.
        This method processes the raw data from the RPLidar,
        filtering out irrelevant distances and angles,
        and converting the data into a format suitable for path planning.

        Parameters
        ----------
        data : NDArray
            The raw data from the RPLidar, expected to be a 2D array
            with angles and distances.
        """
        complexes = []

        for angle, distance in data:

            d_m = distance

            # don't worry about distant objects
            if d_m > self.max_relevant_distance:
                continue

            # first, correctly orient the sensor zero to the robot zero
            angle = angle + self.sensor_mounting_angle
            if angle >= 360.0:
                angle = angle - 360.0
            elif angle < 0.0:
                angle = 360.0 + angle

            # convert the angle from [0 to 360] to [-180 to +180] range
            angle = angle - 180.0

            reflection = False
            for b in self.angles_blanked:
                if angle >= b[0] and angle <= b[1]:
                    # this is a permanent robot reflection
                    # disregard
                    reflection = True
                    break

            if reflection:
                continue

            # bugfix - this calc is based on the [0 to 360]
            # the goal is to save compute, hence want to do the
            # slow math as late as possible
            a_rad = (angle + 180.0) * math.pi / 180.0

            v1 = d_m * math.cos(a_rad)
            v2 = d_m * math.sin(a_rad)

            # convert to x and y
            # x runs backwards to forwards, y runs left to right
            x = -1 * v2
            y = -1 * v1

            # the final data ready to use for path planning
            complexes.append([x, y, angle, d_m])

        array = np.array(complexes)

        # logging.info(f"final: {array.ndim}")

        # sort data into strictly increasing angles to deal with sensor issues
        # the sensor sometimes reports part of the previous scan and part of the next scan
        # so you end up with multiple slightly different values for some angles at the
        # junction

        """
        Determine set of possible paths
        """
        possible_paths = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
        if self.simple_paths:
            # for the turtlebot - it can always turn in place,
            # only question is whether it can advance
            possible_paths = np.array([4])

        if array.ndim > 1:
            # we have valid LIDAR returns

            sorted_indices = array[:, 2].argsort()
            array = array[sorted_indices]

            # logging.debug(f"_process array: {array}")

            X = array[:, 0]
            Y = array[:, 1]
            # A = array[:, 2]
            D = array[:, 3]

            # all the possible conflicting points
            for x, y, d in list(zip(X, Y, D)):
                for apath in possible_paths:
                    for point in self.pp[apath]:
                        p1 = x - point[0]
                        p2 = y - point[1]
                        dist = math.sqrt(p1 * p1 + p2 * p2)
                        # logging.debug(f"_process dist: {dist}")
                        if dist < self.half_width_robot:
                            # too close - this path will not work
                            logging.debug(f"removing path: {apath}")
                            path_to_remove = np.array([apath])
                            possible_paths = np.setdiff1d(
                                possible_paths, path_to_remove
                            )
                            logging.debug(f"remaining paths: {possible_paths}")
                            break  # no need to keep checking this path - we know this path is bad

        logging.debug(f"possible_paths RP Lidar: {possible_paths}")

        self.turn_left = []
        self.turn_right = []
        self.advance = False
        self.retreat = False

        # convert to simple list
        ppl = possible_paths.tolist()

        for p in ppl:
            if p < 4:
                self.turn_left.append(p)
            elif p == 4:
                self.advance = True
            elif p < 9:
                # flip the right turn encoding to make it
                # a mirror of the left hand encoding
                self.turn_right.append(8 - p)
                # so now 8 -> 0, corresponding to a sharp right turn etc
                # so now 5 -> 3, corresponding to a gentle right turn etc
            elif p == 9:
                self.retreat = True

        return_string = "You are surrounded by objects and cannot safely move in any direction. DO NOT MOVE."

        if len(ppl) > 0:
            return_string = "The safe movement directions are: {"
            if self.use_zenoh:  # i.e. you are controlling a TurtleBot4
                if self.advance:
                    return_string += "'turn left', 'turn right', 'move forwards', "
                else:
                    return_string += "'turn left', 'turn right', "
            else:
                if len(self.turn_left) > 0:
                    return_string += "'turn left', "
                if self.advance:
                    return_string += "'move forwards', "
                if len(self.turn_right) > 0:
                    return_string += "'turn right', "
                if self.retreat:
                    return_string += "'move back', "
            return_string += "'stand still'}. "

        self._raw_scan = array
        self._lidar_string = return_string
        self._valid_paths = ppl

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
            if not self.use_zenoh:
                # we are using serial
                try:
                    for i, scan in enumerate(
                        self.lidar.iter_scans_local(
                            scan_type="express",
                            max_buf_meas=0,
                            min_len=25,
                            max_distance_mm=1500,
                        )
                    ):
                        self._preprocess_serial(scan)
                        time.sleep(0.05)
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

    @property
    def movement_options(self) -> Dict[str, List[int]]:
        """
        Get the movement options based on the current valid paths.

        Returns
        -------
        Dict[str, List[int]]
            A dictionary containing lists of valid movement options:
            - 'turn_left': Indices for turning left
            - 'advance': Indices for moving forward
            - 'turn_right': Indices for turning right
            - 'retreat': Indices for moving backward
        """
        return {
            "turn_left": self.turn_left,
            "advance": self.advance,
            "turn_right": self.turn_right,
            "retreat": self.retreat,
        }
