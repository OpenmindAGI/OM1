import logging
import math
import threading
import time
from typing import Optional

import serial
import zenoh

from unitree.unitree_sdk2py.core.channel import ChannelSubscriber
from unitree.unitree_sdk2py.idl.geometry_msgs.msg.dds_ import PoseStamped_
from unitree.unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_
from zenoh_idl import nav_msgs

from .singleton import singleton

rad_to_deg = 57.2958

gOdom = None


def listenerOdom(data):
    global gOdom
    gOdom = nav_msgs.Odometry.deserialize(data.payload.to_bytes())
    logging.debug(f"Odom listener: {gOdom}")


@singleton
class NavigationProvider:
    """
    Navigation Provider.

    # This class implements a singleton pattern to manage RPLidar data streaming.

    # Parameters
    # ----------
    # wait: bool = False
    #     Whether to wait for another class to init this driver, somewhere else in the codebase
    # gps_serial_port: str = "/dev/cu.usbmodem8014"
    #     The name of the serial port in use by the GPS/Mag sensor.
    """

    def __init__(
        self,
        wait: bool = False,
        URID: str = "",
        use_zenoh: bool = False,
        gps_serial_port: str = None,
    ):
        """
        Robot and sensor configuration
        """

        logging.info("Booting Navigation and State Provider")

        if wait:
            # no need to reinit driver
            return

        self.use_zenoh = use_zenoh
        self.URID = URID

        self.session = None
        if self.use_zenoh:
            self.URID = URID
            if URID is None:
                logging.warning(
                    "Aborting TurtleBot4 Navigation system, no URID provided"
                )
                return
            else:
                logging.info(f"TurtleBot4 Navigation system is using URID: {URID}")

            self.cmd_vel = f"{URID}/c3/cmd_vel"

            try:
                self.session = zenoh.open(zenoh.Config())
                logging.info(f"Zenoh navigation provider opened {self.session}")
                logging.info(
                    f"TurtleBot4 navigation listeners starting with URID: {URID}"
                )
                self.session.declare_subscriber(f"{URID}/c3/odom", listenerOdom)
            except Exception as e:
                logging.error(f"Error opening Zenoh client: {e}")

        baudrate = 9600
        timeout = 1  # Optional: set a timeout for reading

        self.ser = None

        if gps_serial_port:
            try:
                # Open the serial port
                self.ser = serial.Serial(gps_serial_port, baudrate, timeout=timeout)
                logging.info(f"Connected to {gps_serial_port} at {baudrate} baud")
            except serial.SerialException as e:
                logging.error(f"Error: {e}")

        # create subscriber
        self.low_state = None
        self.lowstate_subscriber = None

        if not use_zenoh:
            # we are using CycloneDDS
            # e.g. for the Unitree Go2
            self.lowstate_subscriber = ChannelSubscriber("rt/lowstate", LowState_)
            self.lowstate_subscriber.Init(self.lowStateMessageHandler, 10)

            self.pose_subscriber = ChannelSubscriber(
                "rt/utlidar/robot_pose", PoseStamped_
            )
            self.pose_subscriber.Init(self.poseMessageHandler, 10)

        # battery state
        self.battery_percentage = 0.0
        self.battery_voltage = 0.0
        self.battery_amperes = 0.0
        self.battery_temperature = 0

        self.body_height_cm = 0
        self.body_attitude = None

        self._position: Optional[dict] = None

        self.x = 0.0
        self.y = 0.0
        self.z = 0.0

        self.yaw_odom_0_360 = 0.0
        self.yaw_odom_m180_p180 = 0.0
        self.yaw_mag_0_360 = 0.0
        self.yaw_mag_cardinal = ""

        self.running = False
        self._thread: Optional[threading.Thread] = None
        self.start()

    def lowStateMessageHandler(self, msg: LowState_):
        self.low_state = msg

        self.battery_percentage = float(msg.bms_state.soc)
        self.battery_voltage = float(msg.power_v)
        self.battery_amperes = float(msg.power_a)
        self.battery_temperature = int(
            (msg.temperature_ntc1 + msg.temperature_ntc2) / 2
        )

        # other things you can read
        # print("FR_0 motor state: ", msg.motor_state[go2.LegID["FR_0"]])
        # print("IMU state: ", msg.imu_state)
        # print("Battery state: voltage: ", msg.power_v, "current: ", msg.power_a)

    def euler_from_quaternion(self, x, y, z, w):
        """
        https://automaticaddison.com/how-to-convert-a-quaternion-into-euler-angles-in-python/
        Convert a quaternion into euler angles (roll, pitch, yaw)
        roll is rotation around x in radians (counterclockwise)
        pitch is rotation around y in radians (counterclockwise)
        yaw is rotation around z in radians (counterclockwise)
        """
        t0 = +2.0 * (w * x + y * z)
        t1 = +1.0 - 2.0 * (x * x + y * y)
        roll_x = math.atan2(t0, t1)

        t2 = +2.0 * (w * y - z * x)
        t2 = +1.0 if t2 > +1.0 else t2
        t2 = -1.0 if t2 < -1.0 else t2
        pitch_y = math.asin(t2)

        t3 = +2.0 * (w * z + x * y)
        t4 = +1.0 - 2.0 * (y * y + z * z)
        yaw_z = math.atan2(t3, t4)

        return roll_x, pitch_y, yaw_z  # in radians

    def processOdom(self, pose):

        # logging.info(f"pose: {pose}")

        x = pose.orientation.x
        y = pose.orientation.y
        z = pose.orientation.z
        w = pose.orientation.w

        angles = self.euler_from_quaternion(x, y, z, w)

        self.m180_p180 = angles[2] * rad_to_deg * -1.0
        # the * -1.0 changes the heading to sane convention
        # turn right (CW) to INCREASE your heading
        # runs from -180 to + 180, where 0 is the "nose" of the robot

        # runs from 0 to 360
        self.yaw_odom_0_360 = self.m180_p180 + 180.0

        # current position in world frame
        self.x = pose.position.x
        self.y = pose.position.y

        self._position = {
            "x": self.x,
            "y": self.y,
            "yaw_odom_0_360": self.yaw_odom_0_360,
            "yaw_odom_m180_p180": self.m180_p180,
            "yaw_mag_0_360": self.yaw_mag_0_360,
            "yaw_mag_cardinal": self.yaw_mag_cardinal,
            "body_height_cm": self.body_height_cm,
            "body_attitude": self.body_attitude,
        }

        logging.debug(
            f"NAV x,y,yaw_odom,yaw_mag: {round(self.x,2)},{round(self.y,2)},{round(self.yaw_odom_0_360,2)},{round(self.yaw_mag_0_360,2)}"
        )

    def poseMessageHandler(self, msg: PoseStamped_):
        # used by CycloneDDS
        p = msg.pose

        # logging.info(f"poseMessageHandler: {p}")

        self.body_height_cm = round(p.position.z * 100.0)

        # only relevant to dog
        if self.body_height_cm > 24:
            self.body_attitude = "standing"
        elif self.body_height_cm > 3:
            self.body_attitude = "sitting"

        self.processOdom(p)

    def zenohOdomProcessor(self):
        # used by Zenoh
        global gOdom
        if gOdom is not None:
            self.body_height_cm = 0.0
            self.body_attitude = None
            p = gOdom.pose.pose
            self.processOdom(p)

    def magProcessor(self, data):
        value = data.split(" ")
        # HDG (DEG): 102.98 ESE NTC_HDG: 104.83
        if value[0] == "HDG" and len(value) == 6:
            # that's a HDG packet
            self.yaw_mag_0_360 = float(value[2])
            self.yaw_mag_cardinal = value[3]
            logging.debug(f"MAG: {self.yaw_mag_0_360}")

    def start(self):
        """
        Starts the Navigation Provider and processing thread
        if not already running.
        """
        if self._thread and self._thread.is_alive():
            return

        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        """
        Main loop for the Navigation provider.
        """
        while self.running:

            if self.use_zenoh:
                logging.debug("zenohOdomProcessor")
                self.zenohOdomProcessor()
            else:
                logging.info(
                    f"Cyclone Nav Provider: {self.body_height_cm} {self.position}"
                )

            if self.ser:
                # Read a line, decode, and remove whitespace
                data = self.ser.readline().decode("utf-8").strip()
                self.magProcessor(data)
                logging.debug(f"Serial GPS: {data}")

            time.sleep(0.1)

    def stop(self):
        """
        Stop the Navigation provider.
        """
        self.running = False
        if self._thread:
            logging.info("Stopping Navigation provider")
            self._thread.join(timeout=5)

    @property
    def position(self) -> Optional[dict]:
        # """
        # Get the current robot position
        # """
        return self._position
