import logging
import math
import random
import time
from queue import Queue

import zenoh

from actions.base import ActionConfig, ActionConnector
from actions.move_turtle.interface import MoveInput
from providers.rplidar_provider import RPLidarProvider
from zenoh_idl import geometry_msgs, nav_msgs, sensor_msgs

rad_to_deg = 57.2958

gHazard = None
gOdom = None


def listenerHazard(data):
    global gHazard
    gHazard = sensor_msgs.HazardDetectionVector.deserialize(data.payload.to_bytes())
    logging.debug(f"Hazard listener: {gHazard}")


def listenerOdom(data):
    global gOdom
    gOdom = nav_msgs.Odometry.deserialize(data.payload.to_bytes())
    logging.debug(f"Odom listener: {gOdom}")


def euler_from_quaternion(x, y, z, w):
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


class MoveZenohConnector(ActionConnector[MoveInput]):

    def __init__(self, config: ActionConfig):

        super().__init__(config)

        self.angle_tolerance = 5.0
        self.distance_tolerance = 0.05  # m

        self.pending_movements = Queue()

        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
        self.yaw_now = 0.0
        self.hazard = None
        self.emergency = None

        self.session = None

        URID = getattr(self.config, "URID", None)

        if URID is None:
            logging.warning("Aborting TurtleBot4 Move system, no URID provided")
            return
        else:
            logging.info(f"TurtleBot4 Move system is using URID: {URID}")

        self.cmd_vel = f"{URID}/c3/cmd_vel"

        try:
            self.session = zenoh.open(zenoh.Config())
            logging.info(f"Zenoh move client opened {self.session}")
            logging.info(f"TurtleBot4 move listeners starting with URID: {URID}")
            self.session.declare_subscriber(f"{URID}/c3/odom", listenerOdom)
            self.session.declare_subscriber(
                f"{URID}/c3/hazard_detection", listenerHazard
            )
        except Exception as e:
            logging.error(f"Error opening Zenoh client: {e}")

        self.lidar_on = False
        self.lidar = None

        while self.lidar_on is False:
            logging.info("Waiting for RPLidar Provider")
            time.sleep(0.5)
            self.lidar = RPLidarProvider(wait=True)
            self.lidar_on = self.lidar.running
            logging.info(f"TurtleBot4 Action: Lidar running?: {self.lidar_on}")

    def hazardProcessor(self):
        global gHazard
        logging.debug(f"Hazard processor: {gHazard}")
        if gHazard is not None and gHazard.detections and len(gHazard.detections) > 0:
            for haz in gHazard.detections:
                if haz.type == 1:
                    logging.info(
                        f"Hazard Type:{haz.type} direction:{haz.header.frame_id}"
                    )
                    if "right" in haz.header.frame_id:
                        self.hazard = "TURN_LEFT"
                    elif "left" in haz.header.frame_id:
                        self.hazard = "TURN_RIGHT"
                    elif "center" in haz.header.frame_id:
                        if random.randint(1, 2) == 1:
                            self.hazard = "TURN_LEFT"
                        else:
                            self.hazard = "TURN_RIGHT"
                    logging.info(f"Hazard decision: {self.hazard}")

    def odomProcessor(self):
        global gOdom

        # logging.info(f"Odom processor: {gOdom}")

        if gOdom is not None:
            x = gOdom.pose.pose.orientation.x
            y = gOdom.pose.pose.orientation.y
            z = gOdom.pose.pose.orientation.z
            w = gOdom.pose.pose.orientation.w

            # logging.info(f"TurtleBot4 Odom listener: {gOdom.pose.pose.orientation}")

            angles = euler_from_quaternion(x, y, z, w)

            self.yaw_now = angles[2] * rad_to_deg * -1.0

            # we set CW yaw = positive
            # this runs from -180 to +180

            # current position in world frame
            self.x = gOdom.pose.pose.position.x
            self.y = gOdom.pose.pose.position.y

            logging.debug(
                f"TB4 x,y,yaw: {round(self.x,2)},{round(self.y,2)},{round(self.yaw_now,2)}"
            )

    def move(self, vx, vyaw):
        """
        generate movement commands
        """
        logging.debug("move: {} - {}".format(vx, vyaw))

        if self.session is None:
            logging.info("No open Zenoh session, returning")
            return

        logging.debug("Pub twist: {} - {}".format(vx, vyaw))
        t = geometry_msgs.Twist(
            linear=geometry_msgs.Vector3(x=float(vx), y=0.0, z=0.0),
            angular=geometry_msgs.Vector3(x=0.0, y=0.0, z=float(vyaw)),
        )
        self.session.put(self.cmd_vel, t.serialize())

    async def connect(self, output_interface: MoveInput) -> None:

        logging.info(f"AI motion command: {output_interface.action}")

        if self.pending_movements.qsize() > 0:
            logging.info("Movement in progress: disregarding new AI command")
            return

        if self.emergency:
            logging.info("Avoiding barrier: disregarding new AI command")
            return

        if self.x == 0.0:
            # this value is never precisely zero EXCEPT while
            # booting and waiting for data to arrive
            logging.info("Waiting for location data")
            return

        # reconfirm possible paths
        # this is needed due to the 2s latency of the LLMs
        possible_paths = self.lidar.valid_paths
        logging.info(f"Action - Valid paths: {possible_paths}")

        advance_danger = True
        retreat_danger = True

        if 4 in possible_paths:
            advance_danger = False
        if 9 in possible_paths:
            retreat_danger = False

        if output_interface.action == "turn left":
            # turn 90 Deg to the left (CCW)
            target_yaw = self.yaw_now - 90.0
            if target_yaw <= -180:
                target_yaw += 360.0
            self.pending_movements.put([0.0, target_yaw, "turn"])
        elif output_interface.action == "turn right":
            # turn 90 Deg to the right (CW)
            target_yaw = self.yaw_now + 90.0
            if target_yaw >= 180.0:
                target_yaw -= 360.0
            self.pending_movements.put([0.0, target_yaw, "turn"])
        elif output_interface.action == "move forwards":
            if advance_danger:
                return
            self.pending_movements.put([0.5, 0.0, "advance", self.x, self.y])
        elif output_interface.action == "move back":
            if retreat_danger:
                return
            self.pending_movements.put([0.5, 0.0, "retreat", self.x, self.y])
        elif output_interface.action == "stand still":
            logging.info(f"AI movement command: {output_interface.action}")
            # do nothing
        else:
            logging.info(f"AI movement command unknown: {output_interface.action}")

    def tick(self) -> None:

        time.sleep(0.1)

        logging.debug("Move tick")

        self.hazardProcessor()
        self.odomProcessor()

        if self.x == 0.0:
            # this value is never precisely zero except while
            # booting and waiting for data to arrive
            logging.info("Waiting for odom data")
            return

        # physical collision event ALWAYS takes precedence
        if self.hazard is not None:
            if self.hazard == "TURN_RIGHT":
                target_yaw = self.yaw_now + 100.0
                if target_yaw >= 180.0:
                    target_yaw -= 360.0
                self.emergency = target_yaw
            elif self.hazard == "TURN_LEFT":
                target_yaw = self.yaw_now - 100.0
                if target_yaw <= -180:
                    target_yaw += 360.0
                self.emergency = target_yaw
            else:
                logging.error(f"Cannot parse self.hazard: {self.hazard}")

            # clear the hazard flag
            self.hazard = None
            logging.info(f"Should have non-zero avoidance yaw: {self.emergency}")

        if self.emergency:

            target = self.emergency
            logging.info(f"Emergency target: {target}")

            gap = self.yaw_now - target
            if gap > 180.0:
                gap -= 360.0
            elif gap < -180.0:
                gap += 360.0

            """
            gap is a SIGNED value indicating:
                * the direction to turn to get to goal, and
                * the magnitude remaining to turn 

            a mathematically equivalent way to do this is 

            a = targetA - sourceA
            a = (a + 180) % 360 - 180
            where mod = (a, n) -> a - floor(a/n) * n
            """
            logging.info(f"GAP: {gap}")
            if abs(gap) > 10.0:
                logging.debug("gap is big, using large displacements")
                if gap > 0:
                    self.move(0.0, 0.3)
                elif gap < 0:
                    self.move(0.0, -0.3)
            elif abs(gap) > self.angle_tolerance and abs(gap) <= 10.0:
                logging.debug("gap is getting smaller, using smaller steps")
                if gap > 0:
                    self.move(0.0, 0.1)
                elif gap < 0:
                    self.move(0.0, -0.1)
            elif abs(gap) <= self.angle_tolerance:
                logging.info("avoidance motion completed, clear emergency")
                self.emergency = None

            # when there is a hazard, focus on clearing it
            return

        # if we got to this point, we have good data and there is hard wall
        # touch emergency

        target = list(self.pending_movements.queue)

        if len(target) > 0:

            current_target = target[0]

            logging.debug(f"Target: {current_target}")

            goal_dx = current_target[0]
            goal_yaw = current_target[1]
            direction = current_target[2]

            if "turn" in direction:
                gap = self.yaw_now - goal_yaw
                if gap > 180.0:
                    gap -= 360.0
                elif gap < -180.0:
                    gap += 360.0
                logging.debug(f"GAP: {gap}")
                if abs(gap) > 10.0:
                    logging.debug("gap is big, using large displacements")
                    if gap > 0:
                        self.move(0.0, 0.3)
                    elif gap < 0:
                        self.move(0.0, -0.3)
                elif abs(gap) > self.angle_tolerance and abs(gap) <= 10.0:
                    logging.debug("gap is getting smaller, using smaller steps")
                    if gap > 0:
                        self.move(0.0, 0.1)
                    elif gap < 0:
                        self.move(0.0, -0.1)
                elif abs(gap) <= self.angle_tolerance:
                    logging.debug("gap is small enough, done, pop 1 off queue")
                    self.pending_movements.get()
            else:

                # reconfirm possible paths
                pp = self.lidar.valid_paths
                logging.debug(f"Action - Valid paths: {pp}")

                s_x = target[0][3]
                s_y = target[0][4]
                distance_traveled = math.sqrt((self.x - s_x) ** 2 + (self.y - s_y) ** 2)
                remaining = abs(goal_dx - distance_traveled)
                logging.debug(f"distance to advance: {remaining}")

                fb = 0
                if "advance" in direction and 4 in pp:
                    fb = 1
                elif "retreat" in direction and 9 in pp:
                    fb = -1
                else:
                    logging.info("danger, pop 1 off queue")
                    self.pending_movements.get()
                    return

                if remaining > self.distance_tolerance:
                    if distance_traveled < goal_dx:  # keep advancing
                        logging.debug(f"keep moving. remaining:{remaining} ")
                        self.move(fb * 0.4, 0.0)
                    elif distance_traveled > goal_dx:  # you moved too far
                        logging.debug(
                            f"OVERSHOOT: move other way. remaining:{remaining} "
                        )
                        self.move(-1 * fb * 0.1, 0.0)
                else:
                    logging.debug("done, pop 1 off queue")
                    self.pending_movements.get()
