import logging
import math
import time
from queue import Queue
from typing import List, Optional

from actions.base import ActionConfig, ActionConnector, MoveCommand
from actions.move_go2_autonomy.interface import MoveInput
from providers.odom_provider import OdomProvider, RobotState
from providers.rplidar_provider import RPLidarProvider
from unitree.unitree_sdk2py.go2.sport.sport_client import SportClient


class MoveUnitreeSDKConnector(ActionConnector[MoveInput]):

    def __init__(self, config: ActionConfig):
        super().__init__(config)

        self.dog_attitude = None

        # Movement parameters
        self.move_speed = 0.5
        self.turn_speed = 0.8
        self.angle_tolerance = 5.0  # degrees
        self.distance_tolerance = 0.05  # meters
        self.pending_movements: Queue[Optional[MoveCommand]] = Queue()
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
            self.sport_client.StopMove()
            self.sport_client.Move(0.05, 0, 0)
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

        # Process movement commands with lidar safety checks
        movement_map = {
            "turn left": self._process_turn_left,
            "turn right": self._process_turn_right,
            "move forwards": self._process_move_forward,
            "move back": self._process_move_back,
            "stand still": lambda: logging.info("AI movement command: stand still"),
        }

        handler = movement_map.get(output_interface.action)
        if handler:
            handler()
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
        """Cleanly abort current movement and reset state."""
        if self.sport_client:
            self.sport_client.StopMove()
        self.movement_attempts = 0
        if not self.pending_movements.empty():
            self.pending_movements.get()

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
        target: List[MoveCommand] = list(self.pending_movements.queue)

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

            logging.info(f"current_target: {current_target}")

            direction = current_target.direction

            if "turn" in direction:

                gap = self._calculate_angle_gap(
                    self.odom.yaw_odom_m180_p180, current_target.yaw
                )
                logging.info(f"remaining turn GAP: {gap}DEG")

                # Track movement progress
                progress = round(abs(self.gap_previous - gap), 2)
                self.gap_previous = gap
                if self.movement_attempts > 0:
                    logging.info(f"Turn GAP delta: {progress}DEG")
                if abs(gap) > 10.0:
                    logging.debug("gap is big, using large displacements")
                    self.movement_attempts += 1
                    if not self._execute_turn(gap):
                        self.clean_abort()
                        return
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
                goal_dx = current_target.dx
                s_x = current_target.start_x
                s_y = current_target.start_y
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

    def _process_turn_left(self):
        """Process turn left command with safety check."""
        if not self.lidar.turn_left:
            logging.warning("Cannot turn left due to barrier")
            return
        target_yaw = self._normalize_angle(self.odom.yaw_odom_m180_p180 - 90.0)
        self.pending_movements.put(
            MoveCommand(
                dx=0,
                yaw=round(target_yaw, 2),
                direction="turn",
                start_x=round(self.odom.x, 2),
                start_y=round(self.odom.y, 2),
            )
        )
        # [0.0, round(target_yaw, 2), "turn"])

    def _process_turn_right(self):
        """Process turn right command with safety check."""
        if not self.lidar.turn_right:
            logging.warning("Cannot turn right due to barrier")
            return
        target_yaw = self._normalize_angle(self.odom.yaw_odom_m180_p180 + 90.0)
        self.pending_movements.put(
            MoveCommand(
                dx=0,
                yaw=round(target_yaw, 2),
                direction="turn",
                start_x=round(self.odom.x, 2),
                start_y=round(self.odom.y, 2),
            )
        )

    def _process_move_forward(self):
        """Process move forward command with safety check."""
        if not self.lidar.advance:
            logging.warning("Cannot advance due to barrier")
            return
        self.pending_movements.put(
            MoveCommand(
                dx=0.5,
                yaw=0,
                direction="advance",
                start_x=round(self.odom.x, 2),
                start_y=round(self.odom.y, 2),
            )
        )
        # [0.5, 0.0, "advance", round(self.odom.x, 2), round(self.odom.y, 2)]

    def _process_move_back(self):
        """Process move back command with safety check."""
        if not self.lidar.retreat:
            logging.warning("Cannot retreat due to barrier")
            return
        self.pending_movements.put(
            MoveCommand(
                dx=0.5,
                yaw=0,
                direction="retreat",
                start_x=round(self.odom.x, 2),
                start_y=round(self.odom.y, 2),
            )
            # [0.5, 0.0, "retreat", round(self.odom.x, 2), round(self.odom.y, 2)]
        )

    def _normalize_angle(self, angle: float) -> float:
        """Normalize angle to [-180, 180] range."""
        if angle < -180:
            angle += 360.0
        elif angle > 180:
            angle -= 360.0
        return angle

    def _calculate_angle_gap(self, current: float, target: float) -> float:
        """Calculate shortest angular distance between two angles."""
        gap = current - target
        if gap > 180.0:
            gap -= 360.0
        elif gap < -180.0:
            gap += 360.0
        return round(gap, 2)

    def _execute_turn(self, gap: float) -> bool:
        """Execute turn based on gap direction and lidar constraints."""
        if gap > 0:  # Turn left
            if not self.lidar.turn_left:
                logging.warning("Cannot turn left due to barrier")
                return False
            sharpness = min(self.lidar.turn_left)
            self._move_robot(sharpness * 0.15, 0, self.turn_speed)
        else:  # Turn right
            if not self.lidar.turn_right:
                logging.warning("Cannot turn right due to barrier")
                return False
            sharpness = min(self.lidar.turn_right)
            self._move_robot(sharpness * 0.15, 0, -self.turn_speed)
        return True
