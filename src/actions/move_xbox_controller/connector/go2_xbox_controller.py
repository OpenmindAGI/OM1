import logging
import threading
import time
from enum import Enum

from actions.base import ActionConfig, ActionConnector
from actions.move_xbox_controller.interface import IDLEInput
from providers.odom_provider import OdomProvider
from unitree.unitree_sdk2py.go2.sport.sport_client import SportClient

try:
    import hid
except ImportError:
    logging.warning(
        "HID library not found. Please install the HIDAPI library to use this plugin."
    )
    hid = None


class RobotState(Enum):
    STANDING = "standing"
    SITTING = "sitting"


class Go2XboxControllerConnector(ActionConnector[IDLEInput]):
    """
    Xbox controller connector
    """

    def __init__(self, config: ActionConfig):
        """
        Initialize the Xbox controller connector.

        Parameters
        ----------
        config : ActionConfig
            The configuration for the action connector.
        """
        super().__init__(config)

        self.config = config  # never used?

        self.sport_client = None
        try:
            self.sport_client = SportClient()
            self.sport_client.SetTimeout(10.0)
            self.sport_client.Init()
            self.sport_client.StopMove()
            self.sport_client.Move(0.05, 0, 0)
            time.sleep(1)
            logging.info("XBox Unitree sport client initialized")
        except Exception as e:
            self.sport_client = None
            logging.error(f"Error initializing XBox Unitree sport client: {e}")

        self.gamepad = None
        if hid is not None:
            for device in hid.enumerate():
                logging.debug(f"device {device['product_string']}")
                if "Xbox Wireless Controller" in device["product_string"]:
                    vendor_id = device["vendor_id"]
                    product_id = device["product_id"]
                    self.gamepad = hid.Device(vendor_id, product_id)
                    logging.info(
                        f"Connected {device['product_string']} {vendor_id} {product_id}"
                    )
                    break

        if self.gamepad is None:
            logging.warn("Xbox controller not found")

        # Pad buttons
        self.rt_previous = 0
        self.lt_previous = 0
        self.d_pad_previous = 0
        self.button_previous = 0

        self.RTLT_moving = False

        # Movement speed m/s and rad/s (?)
        self.move_speed = 0.5
        self.turn_speed = 0.8

        self.dog_attitude = None

        self.odom = OdomProvider()
        logging.info(f"XBOX Odom Provider: {self.odom}")

        self.thread_lock = threading.Lock()

    def _execute_command_thread(self, command: str) -> None:
        try:
            if command == "StandUp" and self.dog_attitude == RobotState.STANDING:
                logging.info("Already standing, skipping command")
                return
            elif command == "StandDown" and self.dog_attitude == RobotState.SITTING:
                logging.info("Already sitting, skipping command")
                return

            code = getattr(self.sport_client, command)()
            logging.info(f"Unitree command {command} executed with code {code}")

        except Exception as e:
            logging.error(f"Error in command thread {command}: {e}")
        finally:
            self.thread_lock.release()

    def _execute_sport_command_sync(self, command: str) -> None:

        logging.debug(f"_execute_sport_command_sync({command})")

        if self.sport_client is None:
            logging.debug("No sport client, skipping")
            return

        if not self.thread_lock.acquire(blocking=False):
            logging.debug("Action already in progress, skipping")
            return

        try:
            thread = threading.Thread(
                target=self._execute_command_thread, args=(command,), daemon=True
            )
            thread.start()
        except Exception as e:
            logging.error(f"Error executing Unitree command {command}: {e}")
            self.thread_lock.release()

    async def connect(self, output_interface: IDLEInput) -> None:
        """
        Connect to actions from LLM

        Parameters
        ----------
        output_interface : IDLEInput
            The output interface to connect to.

        Returns
        -------
        None
        """
        pass

    def _move_robot(self, vx, vy, vturn=0.0) -> None:
        """
        Move the robot using the sport client.

        Parameters
        ----------
        vx : float
            The speed in the x direction.
        vy : float
            The speed in the y direction.
        vturn : float
            The speed of rotation.

        Returns
        -------
        None
        """
        logging.info(f"XBOX _move_robot: vx={vx}, vy={vy}, vturn={vturn}")

        if not self.sport_client:
            return

        if self.dog_attitude != RobotState.STANDING:
            return

        try:
            logging.info(f"self.sport_client.Move: vx={vx}, vy={vy}, vturn={vturn}")
            self.sport_client.Move(vx, vy, vturn)
        except Exception as e:
            logging.error(f"Error moving robot: {e}")

    def tick(self) -> None:
        """
        Tick function is called periodically to check for input from the Xbox controller.
        It reads the input from the controller and sends the corresponding commands to the robot.

        Returns
        -------
        None
        """
        time.sleep(0.1)
        logging.debug("Gamepad tick")

        if hasattr(self.odom, "running"):
            nav = self.odom.odom
            logging.debug(f"XBOX odom data: {nav}")
            if nav and nav["body_attitude"] == "standing":
                self.dog_attitude = RobotState.STANDING
            else:
                self.dog_attitude = RobotState.SITTING

        data = None

        if self.gamepad:
            # try to read USB data, and if there is nothing, timeout
            # data = list(self.gamepad.read(64, timeout=50))
            data = list(self.gamepad.read(64, timeout=50))

        if data and len(data) > 0:

            logging.debug(f"Gamepad data: {data}")

            # Process triggers for rotation
            lt_value = data[9]  # Left Trigger
            rt_value = data[11]  # Right Trigger
            d_pad_value = data[13]
            button_value = data[14]

            move_triggered_RTLT = False
            move_triggered_dpad = False

            # Trigger values range from 0 to 255
            # Check if the triggers have changed significantly
            # rt_changed = abs(rt_value - self.rt_previous) > 5
            # lt_changed = abs(lt_value - self.lt_previous) > 5

            # Normalize trigger values from 0-255 to 0-1.0
            rt = rt_value / 255.0
            lt = lt_value / 255.0

            previous_RTLT = self.lt_previous + self.rt_previous

            # Right Trigger - clockwise rotation
            if rt > 0.8 and rt > lt:
                self.RTLT_moving = True
                self._move_robot(0.0, 0.0, -self.turn_speed)
            # Left Trigger - counter-clockwise rotation
            elif lt > 0.8 and lt > rt:
                self.RTLT_moving = True
                self._move_robot(0.0, 0.0, self.turn_speed)
            # Both triggers released or below threshold
            elif (rt <= 0.8 and lt <= 0.8) and previous_RTLT > 0.8:
                # we WERE moving, but we just let go of one or both triggers
                move_triggered_RTLT = True
                logging.debug("Triggers released - Stopping rotation")
                if self.sport_client:
                    self.sport_client.StopMove()

            # Update previous Trigger values
            self.rt_previous = rt
            self.lt_previous = lt

            if move_triggered_RTLT:
                # update the previous value of the dpad
                self.d_pad_previous = d_pad_value
                # update the previous value of the button
                self.button_previous = button_value
                # and return, since we just issued a move command in this tick
                return

            # Control robot movement based on D-pad
            logging.debug(f"Gamepad DPAD: {d_pad_value}")

            if d_pad_value == 1:  # Up
                logging.info("D-pad UP - Moving forward")
                move_triggered_dpad = True
                self._move_robot(self.move_speed, 0.0)
            elif d_pad_value == 5:  # Down
                logging.info("D-pad DOWN - Moving backward")
                move_triggered_dpad = True
                self._move_robot(-self.move_speed, 0.0)
            elif d_pad_value == 7:  # Left
                logging.info("D-pad LEFT - Turning left")
                move_triggered_dpad = True
                self._move_robot(0.0, self.turn_speed)
            elif d_pad_value == 3:  # Right
                logging.info("D-pad RIGHT - Turning right")
                move_triggered_dpad = True
                self._move_robot(0.0, -self.turn_speed)
            elif self.d_pad_previous > 0 and d_pad_value == 0:
                # Usewr just released DPAD
                logging.debug("D-pad released - Stopping movement")
                move_triggered_dpad = True
                if self.sport_client:
                    self.sport_client.StopMove()

            # update the value of d_pad_previous
            self.d_pad_previous = d_pad_value

            if move_triggered_dpad:
                self.button_previous = button_value
                # return, since we just issued a DPAD move command in this tick
                return

            # logging.debug(f"Gamepad button value {button_value}")

            if self.button_previous == 0 and button_value > 0:

                # logging.debug(f"Gamepad button pressed")

                # We need this logic because when the user presses a button
                # the gamepad sends a 'press' indication numerous times
                # for several hundred ms, creating numerous
                # duplicated movement commands with a single button press.
                # To prevent this, which would freeze/crash the robot,
                # we only act when the button state changes from 0 to > 0
                # This is basically a software button debounce

                # button A
                if button_value == 1:
                    logging.info("Controller unitree: stand_up")
                    self._execute_sport_command_sync("StandUp")
                # button B
                elif button_value == 2:
                    logging.info("Controller unitree: lay_down")
                    self._execute_sport_command_sync("StandDown")

                # # X button
                # elif button_value == 8:
                #     self._execute_sport_command_sync("Hello")
                #     logging.info("Controller unitree: say_hello")
                # # Y button
                # elif button_value == 16:
                #     self._execute_sport_command_sync("Stretch")
                #     logging.info("Controller unitree: stretch")

                logging.info(f"Gamepad button depressed edge {button_value}")

            # update the value of button_previous
            self.button_previous = button_value

            # no need to return
