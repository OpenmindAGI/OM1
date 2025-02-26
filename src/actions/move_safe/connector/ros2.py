import logging
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
        self.gamepad = None

        self.cb: list[str] = []

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

        if len(self.cb) > 0:
            logging.info(
                f"WARNING - there are manual game controller commands in the queue: {self.cb}"
            )
            return

        if output_interface.action == "stand up":
            logging.info("Unitree AI command: stand up")
            await self._execute_sport_command("StandUp")
        elif output_interface.action == "sit":
            logging.info("Unitree AI command: lay down")
            await self._execute_sport_command("StandDown")
        elif output_interface.action == "shake paw":
            logging.info("Unitree AI command: shake paw")
            await self._execute_sport_command("Hello")
        elif output_interface.action == "stretch":
            logging.info("Unitree AI command: stretch")
            await self._execute_sport_command("Stretch")
        elif output_interface.action == "dance":
            logging.info("Unitree AI command: dance")
            await self._execute_sport_command("Dance1")
        else:
            logging.info(f"Unknown move type: {output_interface.action}")

        logging.info(f"SendThisToROS2: {output_interface.action}")

    def tick(self) -> None:

        time.sleep(0.1)

        if self.gamepad:

            button_now = list(self.gamepad.read(64))[14]

            if self.button_previous == 0 and button_now > 0:
                # YAY - user just pressed a button
                # we need this logic because when the user presses a button
                # the gamepad sends a 'press' indication over and over again
                # for several hundred ms, which would create numerous
                # duplicated movement commands with a single button press
                # to prevent this, we only act when the button state changes from
                # 0 to > 0
                if button_now == 1:
                    self._execute_sport_command_sync("StandUp")
                    logging.info("Controller unitree: stand_up")
                elif button_now == 2:
                    self._execute_sport_command_sync("StandDown")
                    logging.info("Controller unitree: lay_down")
                elif button_now == 8:
                    self._execute_sport_command_sync("Hello")
                    logging.info("Controller unitree: say_hello")
                elif button_now == 16:
                    self._execute_sport_command_sync("Stretch")
                    logging.info("Controller unitree: stretch")
                logging.info(f"Gamepad button depressed edge {button_now}")

            self.button_previous = button_now
