import logging
import math
import time
from queue import Queue

from actions.base import ActionConfig, ActionConnector
from actions.move_go2_autonomy.interface import MoveInput
from providers.odom_provider import OdomProvider, RobotState
from providers.rplidar_provider import RPLidarProvider
from unitree.unitree_sdk2py.go2.sport.sport_client import SportClient


class MoveUnitreeSDKConnector(ActionConnector[MoveInput]):

    def __init__(self, config: ActionConfig):
        super().__init__(config)

        self.dog_attitude = None

        self.move_speed = 0.5
        self.turn_speed = 0.8

        self.angle_tolerance = 5.0
        self.distance_tolerance = 0.05  # m
        self.pending_movements = Queue()
        self.movement_attempts = 0
        self.movement_attempt_limit = 15
        self.gap_previous = 0

        self.lidar = RPLidarProvider()

        # create sport client
        self.sport_client = None
        try:
            self.sport_client = SportClient()
            self.sport_client.SetTimeout(10.0)
            self.sport_client.Init()
            logging.info("Autonomy Unitree sport client initialized")
        except Exception as e:
            logging.error(f"Error initializing Unitree sport client: {e}")

        self.odom = OdomProvider()
        logging.info(f"Autonomy Odom Provider: {self.odom}")

    async def connect(self, output_interface: MoveInput) -> None:

        # this is used only by the LLM
        logging.info(f"AI command.connect: {output_interface.action}")

        if self.odom.moving:
            # for example due to a teleops or game controller command
            logging.info("Disregard new AI movement command - robot is already moving")
            return

        if self.pending_movements.qsize() > 0:
            logging.info("Movement in progress: disregarding new AI command")
            return

        if self.odom.x == 0.0:
            # this value is never precisely zero EXCEPT while
            # booting and waiting for data to arrive
            logging.info("Waiting for location data")
            return

        if output_interface.action == "turn left":
            # turn 90 Deg to the left (CCW)
            if len(self.lidar.turn_left) == 0:
                logging.warning("Cannot turn left due to barrier")
                return
            target_yaw = self.odom.yaw_odom_m180_p180 - 90.0
            if target_yaw <= -180:
                target_yaw += 360.0
            self.pending_movements.put([0.0, round(target_yaw, 2), "turn"])
        elif output_interface.action == "turn right":
            # turn 90 Deg to the right (CW)
            if len(self.lidar.turn_right) == 0:
                logging.warning("Cannot turn right due to barrier")
                return
            target_yaw = self.odom.yaw_odom_m180_p180 + 90.0
            if target_yaw >= 180.0:
                target_yaw -= 360.0
            self.pending_movements.put([0.0, round(target_yaw, 2), "turn"])
        elif output_interface.action == "move forwards":
            if not self.lidar.advance:
                logging.warning("Cannot advance due to barrier")
                return
            self.pending_movements.put(
                [0.5, 0.0, "advance", round(self.odom.x, 2), round(self.odom.y, 2)]
            )
        elif output_interface.action == "move back":
            if not self.lidar.retreat:
                logging.warning("Cannot retreat due to barrier")
                return
            self.pending_movements.put(
                [0.5, 0.0, "retreat", round(self.odom.x, 2), round(self.odom.y, 2)]
            )
        elif output_interface.action == "stand still":
            logging.info(f"AI movement command: {output_interface.action}")
            # do nothing
        else:
            logging.info(f"AI movement command unknown: {output_interface.action}")

        # This is a subset of Go2 movements that are
        # generally safe. Note that the "stretch" action involves
        # about 40 cm of back and forth motion, and the "dance"
        # action involves copious jumping in place for about 10 seconds.

        # if output_interface.action == "stand up":
        #     logging.info("Unitree AI command: stand up")
        #     await self._execute_sport_command("StandUp")
        # elif output_interface.action == "sit":
        #     logging.info("Unitree AI command: lay down")
        #     await self._execute_sport_command("StandDown")
        # elif output_interface.action == "shake paw":
        #     logging.info("Unitree AI command: shake paw")
        #     await self._execute_sport_command("Hello")
        # elif output_interface.action == "stretch":
        #     logging.info("Unitree AI command: stretch")
        #     await self._execute_sport_command("Stretch")
        # elif output_interface.action == "dance":
        #     logging.info("Unitree AI command: dance")
        #     await self._execute_sport_command("Dance1")

    def _move_robot(self, vx, vy, vturn=0.0) -> None:

        logging.info(f"_move_robot: vx={vx}, vy={vy}, vturn={vturn}")

        if not self.sport_client:
            return

        if self.odom.body_attitude != RobotState.STANDING:
            return

        try:
            logging.info(f"self.sport_client.Move: vx={vx}, vy={vy}, vturn={vturn}")
            self.sport_client.Move(vx, vy, vturn)
        except Exception as e:
            logging.error(f"Error moving robot: {e}")

    def clean_abort(self) -> None:
        if self.sport_client:
            self.sport_client.StopMove()
        self.movement_attempts = 0
        self.pending_movements.get()
        # pop 1 off the pending queue
        # move to next command

    def tick(self) -> None:

        logging.debug("AI Motion Tick")

        if self.odom.odom is None:
            # this value is never precisely None except while
            # booting and waiting for data to arrive
            logging.info("Waiting for odom data")
            time.sleep(0.5)
            return

        if self.odom.x == 0.0:
            # this value is never precisely zero except while
            # booting and waiting for data to arrive
            logging.info("Waiting for odom data")
            time.sleep(0.5)
            return

        if self.odom.body_attitude != RobotState.STANDING:
            logging.info("Cannot move - dog is sitting")
            time.sleep(0.5)
            return

        # if we got to this point, we have good data and we are able to
        # safely proceed
        target = list(self.pending_movements.queue)

        if len(target) > 0:

            current_target = target[0]

            logging.info(
                f"Target: {current_target} current yaw: {round(self.odom.yaw_odom_m180_p180,2)}"
            )

            if self.movement_attempts > self.movement_attempt_limit:
                # abort - we are not converging
                self.clean_abort()
                logging.info(
                    f"TIMEOUT - AI movement timeout - not converging after {self.movement_attempt_limit} attempts- issued StopMove()"
                )
                return

            goal_dx = current_target[0]
            goal_yaw = current_target[1]
            direction = current_target[2]

            if "turn" in direction:
                gap = self.odom.yaw_odom_m180_p180 - goal_yaw
                if gap > 180.0:
                    gap -= 360.0
                elif gap < -180.0:
                    gap += 360.0
                gap = round(gap, 2)
                logging.info(f"remaining turn GAP: {gap}DEG")

                # check for responsivity of movement platform
                # is the robot frozen/stuck?
                progress = round(abs(self.gap_previous - gap), 2)
                self.gap_previous = gap
                if self.movement_attempts > 0:
                    logging.info(f"Turn GAP delta: {progress}DEG")
                    # if progress < 1.0:  # deg
                    #     # we might be stuck or something else is wrong
                    #     self.clean_abort()
                    #     return
                if abs(gap) > 10.0:
                    logging.debug("gap is big, using large displacements")
                    self.movement_attempts += 1
                    if gap > 0:
                        if len(self.lidar.turn_left) == 0:
                            logging.warning("Cannot turn left due to barrier")
                            self.clean_abort()
                            return
                        sharpness = min(self.lidar.turn_left)
                        # this can be 0, 1, 2, or 3
                        # turn combines forward motion with rotation
                        self._move_robot(sharpness * 0.15, 0, self.turn_speed)
                    elif gap < 0:
                        if len(self.lidar.turn_right) == 0:
                            logging.warning("Cannot turn right due to barrier")
                            self.clean_abort()
                            return
                        sharpness = min(self.lidar.turn_right)
                        # this can be 0, 1, 2, or 3
                        # turn combines forward motion with rotation
                        self._move_robot(sharpness * 0.15, 0, -1 * self.turn_speed)
                elif abs(gap) > self.angle_tolerance and abs(gap) <= 10.0:
                    logging.debug("gap is getting smaller, using smaller steps")
                    self.movement_attempts += 1
                    # rotate only because we are so close
                    # no need to check barriers because we are just performing small rotations
                    if gap > 0:
                        self._move_robot(0, 0, 0.2)
                    elif gap < 0:
                        self._move_robot(0, 0, -0.2)
                elif abs(gap) <= self.angle_tolerance:
                    logging.info(
                        "turn completed normally, processing next AI movement command"
                    )
                    self.clean_abort()
            else:
                s_x = target[0][3]
                s_y = target[0][4]
                distance_traveled = math.sqrt(
                    (self.odom.x - s_x) ** 2 + (self.odom.y - s_y) ** 2
                )
                gap = round(abs(goal_dx - distance_traveled), 2)
                progress = round(abs(self.gap_previous - gap), 2)
                self.gap_previous = gap
                if self.movement_attempts > 0:
                    logging.info(f"Forward/retreat GAP delta: {progress}m")
                    # if progress < 0.03:  # cm
                    #     # we might be stuck or something else is wrong
                    #     self.clean_abort()
                    #     return

                fb = 0
                if "advance" in direction and self.lidar.advance:
                    fb = 1
                elif "retreat" in direction and self.lidar.retreat:
                    fb = -1
                else:
                    logging.info("advance/retreat danger, pop 1 off queue")
                    self.clean_abort()
                    return

                if gap > self.distance_tolerance:
                    self.movement_attempts += 1
                    if distance_traveled < goal_dx:  # keep advancing
                        logging.info(f"keep moving. remaining:{gap}m ")
                        self._move_robot(fb * self.move_speed, 0.0, 0.0)
                    elif distance_traveled > goal_dx:  # you moved too far
                        logging.debug(f"OVERSHOOT: move other way. remaining:{gap}m")
                        self._move_robot(-1 * fb * 0.2, 0.0, 0.0)
                else:
                    logging.info(
                        "advance/retreat completed normally, processing next AI movement command"
                    )
                    self.clean_abort()

        time.sleep(0.1)
