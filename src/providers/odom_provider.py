import logging
import math
from enum import Enum
from typing import Optional, Union

import zenoh

try:
    # Needed for Unitree but not TurtleBot4
    from unitree.unitree_sdk2py.core.channel import ChannelSubscriber
    from unitree.unitree_sdk2py.idl.geometry_msgs.msg.dds_ import PoseStamped_
except ImportError:
    logging.warning(
        "Unitree SDK or CycloneDDS not found. You do not need this unless you are connecting to a Unitree robot."
    )

from zenoh_idl import nav_msgs
from zenoh_idl.geometry_msgs import PoseWithCovariance
from zenoh_idl.nav_msgs import Odometry

from .singleton import singleton

rad_to_deg = 57.2958


class RobotState(Enum):
    STANDING = "standing"
    SITTING = "sitting"


@singleton
class OdomProvider:
    """
    Odom Provider.

    This class implements a singleton pattern to manage:
        * Odom and pose data using either Zenoh or CycloneDDS

    Parameters
    ----------
    URID: str = ""
        The URID needed to connect to the right Zenoh publisher in the local network
    use_zenoh: bool = False
        If true, get odom/pose data from Zenoh - typically used by TurtleBot4
        Otherwise, use CycloneDDS
    """

    def __init__(self, URID: str = "", use_zenoh: bool = False):
        """
        Robot and sensor configuration
        """

        logging.info("Booting Odom Provider")

        self.use_zenoh = use_zenoh
        self.URID = URID

        if self.use_zenoh:
            # typically, TurtleBot4
            if URID is None:
                logging.warning(
                    "Aborting TurtleBot4 Navigation system, no URID provided"
                )
                return
            else:
                logging.info(f"TurtleBot4 Navigation system is using URID: {URID}")

            try:
                self.session = zenoh.open(zenoh.Config())
                logging.info(f"Zenoh navigation provider opened {self.session}")
                logging.info(
                    f"TurtleBot4 navigation listeners starting with URID: {URID}"
                )
                self.session.declare_subscriber(
                    f"{URID}/c3/odom", self.zenoh_odom_handler
                )
            except Exception as e:
                logging.error(f"Error opening Zenoh client: {e}")
        else:
            # we are using CycloneDDS e.g. for the Unitree Go2
            try:
                self.pose_subscriber = ChannelSubscriber(
                    "rt/utlidar/robot_pose", PoseStamped_
                )
                self.pose_subscriber.Init(self.pose_message_handler, 10)
            except Exception as e:
                logging.error(f"Error opening CycloneDDS client: {e}")

        self.body_height_cm = 0
        self.body_attitude: Optional[RobotState] = None

        self.moving: bool = False
        self.previous_x = 0
        self.previous_y = 0
        self.previous_z = 0
        self.move_history = 0

        self._odom: Optional[Union[Odometry, PoseStamped_]] = None

        self.x = 0.0
        self.y = 0.0
        self.z = 0.0

        self.yaw_odom_0_360 = 0.0
        self.yaw_odom_m180_p180 = 0.0

    def zenoh_odom_handler(self, data: zenoh.Sample):
        """
        Zenoh odom handler.

        Parameters
        ----------
        data : zenoh.Sample
            The data received from the Zenoh subscriber.
        """
        self._odom: Odometry = nav_msgs.Odometry.deserialize(data.payload.to_bytes())
        logging.debug(f"Odom listener: {self._odom}")

        p = self._odom.pose.pose
        self.process_odom(p)

    def pose_message_handler(self, msg: PoseStamped_):
        """
        Unitree pose message handler.

        Parameters
        ----------
        msg : PoseStamped_
            The message containing the pose data.
        """
        self._odom = msg
        logging.debug(f"Pose listener: {self._odom}")

        p = self._odom.pose
        self.body_height_cm = round(p.position.z * 100.0)

        # only relevant to dog
        if self.body_height_cm > 24:
            self.body_attitude = RobotState.STANDING
        elif self.body_height_cm > 3:
            self.body_attitude = RobotState.SITTING

        self.process_odom(p)

    def euler_from_quaternion(self, x: float, y: float, z: float, w: float) -> tuple:
        """
        https://automaticaddison.com/how-to-convert-a-quaternion-into-euler-angles-in-python/
        Convert a quaternion into euler angles (roll, pitch, yaw)
        roll is rotation around x in radians (counterclockwise)
        pitch is rotation around y in radians (counterclockwise)
        yaw is rotation around z in radians (counterclockwise)

        Parameters
        ----------
        x : float
            The x component of the quaternion.
        y : float
            The y component of the quaternion.
        z : float
            The z component of the quaternion.
        w : float
            The w component of the quaternion.

        Returns
        -------
        tuple
            A tuple containing the roll, pitch, and yaw angles in radians.
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

    def process_odom(self, pose: PoseWithCovariance):
        """
        Process the odom data and update the internal state.

        Parameters
        ----------
        pose : PoseWithCovariance
            The pose data containing position and orientation.
        """
        logging.debug(f"pose: {pose}")

        x = pose.orientation.x
        y = pose.orientation.y
        z = pose.orientation.z
        w = pose.orientation.w

        dx = (pose.position.x - self.previous_x) ** 2
        dy = (pose.position.y - self.previous_y) ** 2
        dz = (pose.position.z - self.previous_z) ** 2

        self.previous_x = pose.position.x
        self.previous_y = pose.position.y
        self.previous_z = pose.position.z

        delta = math.sqrt(dx + dy + dz)

        # moving? Use a decay kernal
        self.move_history = 0.4 * delta + 0.6 * self.move_history

        if delta > 0.01 or self.move_history > 0.005:
            # we want to detect movement quickly (and flip "moving" False->True), but
            # wait for the platform to stabilize before we flip "moving" True->False
            self.moving = True
            logging.info(
                f"delta moving (m): {round(delta,3)} {round(self.move_history,3)}"
            )
        else:
            self.moving = False

        angles = self.euler_from_quaternion(x, y, z, w)

        self.yaw_odom_m180_p180 = angles[2] * rad_to_deg * -1.0
        # the * -1.0 changes the heading to sane convention
        # turn right (CW) to INCREASE your heading
        # runs from -180 to + 180, where 0 is the "nose" of the robot

        # runs from 0 to 360
        self.yaw_odom_0_360 = self.yaw_odom_m180_p180 + 180.0

        # current position in world frame
        self.x = pose.position.x
        self.y = pose.position.y

    @property
    def odom(self) -> Optional[Union[Odometry, PoseStamped_]]:
        """
        Get the current odometry data.

        Returns
        -------
        Optional[Union[Odometry, PoseStamped_]]
            The current odometry data if available, otherwise None.
        """
        return self._odom

    @property
    def position(self) -> dict:
        """
        Get the current robot position in world frame.
        Returns a dictionary with x, y, and yaw_odom_0_360.

        Returns
        -------
        dict
            A dictionary containing the current position and orientation of the robot.
            Keys include:
            - x: The x coordinate of the robot in the world frame.
            - y: The y coordinate of the robot in the world frame.
            - moving: A boolean indicating if the robot is currently moving.
            - yaw_odom_0_360: The yaw angle of the robot in degrees, ranging from 0 to 360.
            - body_height_cm: The height of the robot's body in centimeters.
            - body_attitude: The current attitude of the robot (e.g., sitting or standing).
        """
        return {
            "x": self.x,
            "y": self.y,
            "moving": self.moving,
            "yaw_odom_0_360": self.yaw_odom_0_360,
            "body_height_cm": self.body_height_cm,
            "body_attitude": self.body_attitude,
        }
