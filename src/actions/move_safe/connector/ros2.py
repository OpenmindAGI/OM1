import logging
import os
import time

import hid
from unitree.unitree_sdk2py.go2.sport.sport_client import SportClient

from actions.base import ActionConfig, ActionConnector
from actions.move_safe.interface import MoveInput


class MoveRos2Connector(ActionConnector[MoveInput]):

    def __init__(self, config: ActionConfig):
        super().__init__(config)

        self.joysticks = []

        self.vendor_id = ""
        self.product_id = ""
        self.button_previous = None
        self.gamepad = None

        self.cb: list[str] = []

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

        self.UNIEN0 = os.getenv("UNITREE_WIRED_ETHERNET")
        if self.UNIEN0 is not None and self.UNIEN0 != "SIM":
            # Set up Unitree subscriber unless adapater is set to "SIM""
            # ChannelFactoryInitialize(0, self.UNITREE_WIRED_ETHERNET)
            # this can only be done once, at top level
            logging.info(
                f"Move system using {self.UNIEN0} as the network Ethernet adapter"
            )
            self.sport_client = SportClient()
            self.sport_client.SetTimeout(10.0)
            self.sport_client.Init()

    async def connect(self, output_interface: MoveInput) -> None:

        if len(self.cb) > 0:
            logging.info(
                f"WARNING - there are manual game controller commands in the queue: {self.cb}"
            )
            return

        if output_interface.action == "stand up":
            logging.info("Unitree AI command: stand up")
            if self.sport_client:
                self.sport_client.StandUp()
        elif output_interface.action == "sit":
            logging.info("Unitree AI command: lay down")
            if self.sport_client:
                self.sport_client.StandDown()
        elif output_interface.action == "shake paw":
            logging.info("Unitree AI command: shake paw")
            if self.sport_client:
                self.sport_client.Hello()
        else:
            logging.info(f"Unknown move type: {output_interface.action}")
            # raise ValueError(f"Unknown move type: {output_interface.action}")

        logging.info(f"SendThisToROS2: {output_interface.action}")

    def tick(self) -> None:

        time.sleep(0.1)

        # logging.info("MoveRos2Connector Tick")

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
                    if len(self.cb) == 0 or self.cb[-1] != "game_a":
                        self.cb.append("game_a")
                elif button_now == 2:
                    if len(self.cb) == 0 or self.cb[-1] != "game_b":
                        self.cb.append("game_b")
                elif button_now == 8:
                    if len(self.cb) == 0 or self.cb[-1] != "game_x":
                        self.cb.append("game_x")
                elif button_now == 16:
                    if len(self.cb) == 0 or self.cb[-1] != "game_y":
                        self.cb.append("game_y")
                logging.info(f"Gamepad button depressed edge {self.cb}")

            self.button_previous = button_now

        if len(self.cb) > 0:

            if self.cb[-1] == "game_a":
                logging.info("ROS2 unitree: stand_up")
                if self.sport_client:
                    self.sport_client.StandUp()
                del self.cb[-1]
            elif self.cb[-1] == "game_b":
                if self.sport_client:
                    self.sport_client.StandDown()
                logging.info("ROS2 unitree: lay_down")
                del self.cb[-1]
            elif self.cb[-1] == "game_x":
                if self.sport_client:
                    self.sport_client.Hello()
                logging.info("ROS2 unitree: say_hello")
                del self.cb[-1]
            elif self.cb[-1] == "game_y":
                if self.sport_client:
                    self.sport_client.Stretch()
                logging.info("ROS2 unitree: stretch")
                del self.cb[-1]
