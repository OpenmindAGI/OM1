import logging
import threading
import time
from enum import Enum
import random

from actions.base import ActionConfig, ActionConnector
from actions.move_safe_lidar.interface import MoveInput
from unitree.unitree_sdk2py.go2.sport.sport_client import SportClient
from providers.rplidar_provider import RPLidarProvider
from providers.navigation_provider import NavigationProvider

class RobotState(Enum):
    STANDING = "standing"
    SITTING = "sitting"

class MoveRos2Connector(ActionConnector[MoveInput]):

    def __init__(self, config: ActionConfig):
        super().__init__(config)

        self.current_state = RobotState.STANDING

        self.move_speed = 0.7
        self.turn_speed = 0.6

        self.lidar_on = False
        self.lidar = None

        lidar_timeout = 10  # if the LIDAR does not connect in 5 seconds, we assume there is no LIDAR
        lidar_attempts = 0

        while self.lidar_on is False:
            logging.info(f"Waiting for RPLidar Provider. Attempt: {lidar_attempts}")
            self.lidar = RPLidarProvider(wait=True)
            self.lidar_on = self.lidar.running
            logging.info(f"Action: Lidar running?: {self.lidar_on}")
            lidar_attempts += 1
            if lidar_attempts > lidar_timeout:
                logging.warning(
                    f"RPLidar Provider timeout after {lidar_attempts} attempts - no LIDAR - DANGEROUS"
                )
                break
            time.sleep(0.5)

        self.motion_buffer = None

        # create sport client
        self.sport_client = None
        try:
            self.sport_client = SportClient()
            self.sport_client.SetTimeout(10.0)
            self.sport_client.Init()
            logging.info("Unitree sport client initialized")
        except Exception as e:
            logging.error(f"Error initializing Unitree sport client: {e}")

        self.navigation_on = False
        self.navigation = None
        
        navigation_timeout = 10
        navigation_attempts = 0

        while not self.navigation_on:
            logging.info(f"Waiting for Navigation Provider. Attempt: {navigation_attempts}")
            self.navigation = NavigationProvider(wait=False)
            if hasattr(self.navigation, 'running'):
                self.navigation_on = self.navigation.running
                logging.info(f"Action: navigation running?: {self.navigation_on}")
            else:
                logging.info("Action: waiting for navigation")
            navigation_attempts += 1
            if navigation_attempts > navigation_timeout:
                logging.warning(
                    f"Navigation Provider timeout after {navigation_attempts} attempts - no Navigation - DANGEROUS"
                )
                break
            time.sleep(0.5)

        self.thread_lock = threading.Lock()

    def _execute_command_thread(self, command: str) -> None:
        try:
            if command == "StandUp" and self.current_state == RobotState.STANDING:
                logging.info("Already standing, skipping command")
                return
            elif command == "StandDown" and self.current_state == RobotState.SITTING:
                logging.info("Already sitting, skipping command")
                return

            code = getattr(self.sport_client, command)()
            logging.info(f"Unitree command {command} executed with code {code}")

            if command == "StandUp":
                self.current_state = RobotState.STANDING
            elif command == "StandDown":
                self.current_state = RobotState.SITTING

        except Exception as e:
            logging.error(f"Error in command thread {command}: {e}")
        finally:
            self.thread_lock.release()

    def _execute_sport_command_sync(self, command: str) -> None:
        if not self.sport_client:
            return

        if not self.thread_lock.acquire(blocking=False):
            logging.info("Action already in progress, skipping")
            return

        try:
            thread = threading.Thread(
                target=self._execute_command_thread, args=(command,), daemon=True
            )
            thread.start()
        except Exception as e:
            logging.error(f"Error executing Unitree command {command}: {e}")
            self.thread_lock.release()

    async def _execute_sport_command(self, command: str) -> None:
        if not self.sport_client:
            return

        if not self.thread_lock.acquire(blocking=False):
            logging.info("Action already in progress, skipping")
            return

        try:
            thread = threading.Thread(
                target=self._execute_command_thread, args=(command,), daemon=True
            )
            thread.start()
        except Exception as e:
            logging.error(f"Error executing Unitree command {command}: {e}")
            self.thread_lock.release()

    async def connect(self, output_interface: MoveInput) -> None:

        # this is used only by the LLM
        logging.info(f"AI command.connect: {output_interface.action}")

        turn_left = []
        advance = []
        turn_right = []
        retreat = []

        if self.lidar:
            possible_paths = self.lidar.valid_paths
            logging.info(f"Action - Valid paths: {possible_paths}")
            for p in possible_paths:
                if p < 4:
                    turn_left.append(p)
                elif p == 4:
                    advance.append(p)
                elif p < 9:
                    turn_right.append(p)
                elif p == 9:
                    retreat.append(p)

        if output_interface.action == "turn left":
            logging.info("Unitree AI command: turn left")
            if len(turn_left) > 0:
                path = random.choice(turn_left)
                self.motion_buffer = ["TurnLeft", path]
            else:
                logging.warning("Cannot turn left due to barrier")
        elif output_interface.action == "turn right":
            logging.info("Unitree AI command: turn right")
            if len(turn_right) > 0:
                path = random.choice(turn_right)
                self.motion_buffer = ["TurnRight", path]
            else:
                logging.warning("Cannot turn right due to barrier")
        elif output_interface.action == "move forwards":
            logging.info("Unitree AI command: move forwards")
            if len(advance) > 0:
                self.motion_buffer = ["MoveForwards", 0]
            else:
                logging.warning("Cannot advance due to barrier")
        elif output_interface.action == "move back":
            logging.info("Unitree AI command: move back")
            if len(retreat) > 0:
                self.motion_buffer = ["MoveBack", 0]
            else:
                logging.warning("Cannot retreat due to barrier")
        elif output_interface.action == "stand still":
            logging.info("Unitree AI command: stand still")
            self.motion_buffer = ["StandStill", 0]
            # do nothing
        else:
            logging.info(f"Unknown move type: {output_interface.action}")

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

        #logging.info(f"AI command: {output_interface.action}")

    def _move_robot(self, vx, vy, vturn=0.0) -> None:
        
        logging.info(
            f"_move_robot: vx={vx}, vy={vy}, vturn={vturn}"
        )

        if not self.sport_client or self.current_state != RobotState.STANDING:
            return

        try:
            logging.info(
                f"self.sport_client.Move: vx={vx}, vy={vy}, vturn={vturn}"
            )
            # self.sport_client.Move(vx, vy, vturn)
        except Exception as e:
            logging.error(f"Error moving robot: {e}")

    def tick(self) -> None:

        logging.info(f"AI Motion Tick")

        if self.motion_buffer:
            logging.info(f"Motion Buffer: {self.motion_buffer}")

        time.sleep(0.1)
