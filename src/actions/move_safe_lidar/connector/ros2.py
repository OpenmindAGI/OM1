import logging
import random
import threading
import time
from enum import Enum

try:
    import hid
except ImportError:
    logging.warning(
        "HID library not found. Please install the HIDAPI library to use this plugin."
    )
    hid = None

from actions.base import ActionConfig, ActionConnector
from actions.move_safe.interface import MoveInput
from providers.rplidar_provider import RPLidarProvider
from unitree.unitree_sdk2py.go2.sport.sport_client import SportClient


class RobotState(Enum):
    STANDING = "standing"
    SITTING = "sitting"


class MoveRos2Connector(ActionConnector[MoveInput]):

    def __init__(self, config: ActionConfig):
        super().__init__(config)

        self.current_state = RobotState.STANDING

        self.joysticks = []

        self.vendor_id = ""
        self.product_id = ""
        self.button_previous = None
        self.d_pad_previous = None
        self.rt_previous = 0
        self.lt_previous = 0
        self.gamepad = None

        self.move_speed = 0.7
        self.turn_speed = 0.6

        self.motion_buffer = None

        if hid is not None:
            for device in hid.enumerate():
                logging.debug(f"device {device['product_string']}")
                if "Xbox Wireless Controller" in device["product_string"]:
                    self.vendor_id = device["vendor_id"]
                    self.product_id = device["product_id"]
                    self.gamepad = hid.Device(self.vendor_id, self.product_id)
                    logging.info(
                        f"Connected {device['product_string']} {self.vendor_id} {self.product_id}"
                    )
                    break

        self.lidar_on = False
        self.lidar = None

        while self.lidar_on is False:
            logging.info("Waiting for RPLidar Provider")
            time.sleep(0.5)
            self.lidar = RPLidarProvider(wait=True)
            self.lidar_on = self.lidar.running
            logging.info(f"Action: Lidar running?: {self.lidar_on}")

        # create sport client
        self.sport_client = None
        try:
            self.sport_client = SportClient()
            self.sport_client.SetTimeout(10.0)
            self.sport_client.Init()
            logging.info("Unitree sport client initialized")
        except Exception as e:
            logging.error(f"Error initializing Unitree sport client: {e}")

        self.thread_lock = threading.Lock()

    def _execute_command_thread(self, command: str) -> None:

        if not self.sport_client:
            return

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

    async def _execute_sport_command(self, command: str) -> None:

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

        logging.info(f"AI command: {output_interface.action}")

        possible_paths = self.lidar.valid_paths
        logging.info(f"Action - Valid paths: {possible_paths}")

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
                logging.warning("Cannot turn right to barrier")
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

        logging.info(f"AI command: {output_interface.action}")

    def _move_robot(self, vx, vy, vturn=0.0) -> None:

        logging.info(
            f"Moving robot goal: move_speed_x={vx}, move_speed_y={vy}, rotate_speed={vturn}"
        )

        if not self.sport_client or self.current_state != RobotState.STANDING:
            return

        try:
            logging.info(
                f"SENDING: move_speed_x={vx}, move_speed_y={vy}, rotate_speed={vturn}"
            )
            sport_client = SportClient()
            sport_client.Init()
            sport_client.Move(vx, vy, vturn)
        except Exception as e:
            logging.error(f"Error moving robot: {e}")

    def tick(self) -> None:

        time.sleep(0.1)

        if self.gamepad:

            data = list(self.gamepad.read(64))
            # Process triggers for rotation
            # RT is typically on byte 9, LT on byte 8 for Xbox controllers
            rt_value = data[11]  # Right Trigger
            lt_value = data[9]  # Left Trigger

            # Trigger values usually range from 0 to 255
            # Check if the triggers have changed significantly
            rt_changed = abs(rt_value - self.rt_previous) > 5
            lt_changed = abs(lt_value - self.lt_previous) > 5

            if rt_changed or lt_changed:
                # Update previous values
                self.rt_previous = rt_value
                self.lt_previous = lt_value

                # Normalize trigger values from 0-255 to 0-1.0
                rt_normalized = rt_value / 255.0
                lt_normalized = lt_value / 255.0

                # stop other motions
                self.motion_buffer = None

                # Right Trigger - clockwise rotation
                if rt_normalized > 0.8 and rt_normalized > lt_normalized:
                    self._move_robot(0.0, 0.0, -self.turn_speed)

                # Left Trigger - counter-clockwise rotation
                elif lt_normalized > 0.8 and lt_normalized > rt_normalized:
                    self._move_robot(0.0, 0.0, self.turn_speed)

                # Both triggers released or below threshold
                elif rt_normalized <= 0.8 and lt_normalized <= 0.8:
                    logging.debug("Triggers released - Stopping rotation")
                    self._move_robot(0.0, 0.0)

            d_pad_value = data[13]
            if d_pad_value != self.d_pad_previous:
                self.d_pad_previous = d_pad_value

                # stop other motions
                self.motion_buffer = None

                # Control robot movement based on D-pad
                if d_pad_value == 1:  # Up
                    logging.info("D-pad UP - Moving forward")
                    self._move_robot(self.move_speed, 0.0)
                elif d_pad_value == 5:  # Down
                    logging.info("D-pad DOWN - Moving backward")
                    self._move_robot(-self.move_speed, 0.0)
                elif d_pad_value == 7:  # Left
                    logging.info("D-pad LEFT - Turning left")
                    self._move_robot(0.0, self.move_speed)
                elif d_pad_value == 3:  # Right
                    logging.info("D-pad RIGHT - Turning right")
                    self._move_robot(0.0, -self.move_speed)
                elif d_pad_value == 0:  # Nothing pressed
                    logging.debug("D-pad released - Stopping movement")
                    self._move_robot(0.0, 0.0)

            button_value = data[14]

            if self.button_previous == 0 and button_value > 0:
                # User just pressed a button

                # stop other motion
                self.motion_buffer = None

                # We need this logic because when the user presses a button
                # the gamepad sends a 'press' indication numerous times
                # for several hundred ms, creating numerous
                # duplicated movement commands with a single button press.
                # To prevent this, which would freeze/crash the robot,
                # we only act when the button state changes from 0 to > 0
                # This is basically a software button debounce

                # A button
                if button_value == 1:
                    self._execute_sport_command("StandUp", 0)
                    logging.info("Controller unitree: stand_up")
                # B button
                elif button_value == 2:
                    self._execute_sport_command("StandDown", 0)
                    logging.info("Controller unitree: lay_down")
                # X button
                elif button_value == 8:
                    self._execute_sport_command("Hello", 0)
                    logging.info("Controller unitree: say_hello")
                # Y button
                elif button_value == 16:
                    self._execute_sport_command("Stretch", 0)
                    logging.info("Controller unitree: stretch")

                logging.info(f"Gamepad button depressed edge {button_value}")

            self.button_previous = button_value

        if self.motion_buffer:

            logging.info(f"MOTION BUFFER {self.motion_buffer}")

            possible_paths = self.lidar.valid_paths
            # check for new possible collisons right before each move
            logging.info(f"FAST - Valid paths: {possible_paths}")

            if self.motion_buffer[0] == "TurnLeft":
                turn_type = self.motion_buffer[1]
                if turn_type not in possible_paths:
                    return
                turn_rate = 0.1 * (4 - turn_type)
                self._move_robot(self.move_speed, 0.0, turn_rate)
            elif self.motion_buffer[0] == "MoveForwards":
                if 5 not in possible_paths:
                    return
                self._move_robot(self.move_speed, 0.0, 0.0)
            elif self.motion_buffer[0] == "TurnRight":
                turn_type = self.motion_buffer[1]
                if turn_type not in possible_paths:
                    return
                turn_rate = -0.1 * (turn_type - 4)
                self._move_robot(self.move_speed, 0.0, turn_rate)
            elif self.motion_buffer[0] == "MoveBack":
                if 9 not in possible_paths:
                    return
                self._move_robot(-self.move_speed, 0.0, 0.0)
            elif self.motion_buffer[0] == "StandStill":
                logging.info("Standing Still")
