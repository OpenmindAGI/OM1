import logging
import time

from actions.base import ActionConfig, ActionConnector
from actions.move_xbox_controller.interface import IDLEInput
from unitree.unitree_sdk2py.go2.sport.sport_client import SportClient

try:
    import hid
except ImportError:
    logging.warning(
        "HID library not found. Please install the HIDAPI library to use this plugin."
    )
    hid = None


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

        self.config = config

        self.sport_client = SportClient()
        self.sport_client.Init()

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

        # Pad buttons
        self.rt_previous = 0
        self.lt_previous = 0
        self.d_pad_previous = 0

        # Movement speed
        self.move_speed = 0.5
        self.turn_speed = 0.5

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

    def _move_robot(
        self, move_speed_x: float, move_speed_y: float, rotate_speed: float = 0.0
    ) -> None:
        """
        Move the robot using the sport client.

        Parameters
        ----------
        move_speed_x : float
            The speed in the x direction.
        move_speed_y : float
            The speed in the y direction.
        rotate_speed : float
            The speed of rotation.

        Returns
        -------
        None
        """
        try:
            if move_speed_x == 0.0 and move_speed_y == 0.0 and rotate_speed == 0.0:
                return
            logging.debug(
                f"Moving robot: move_speed_x={move_speed_x}, move_speed_y={move_speed_y}, rotate_speed={rotate_speed}"
            )
            self.sport_client.Move(move_speed_x, move_speed_y, rotate_speed)
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
        if self.gamepad:
            data = list(self.gamepad.read(64))

            lt_value = data[9]
            rt_value = data[11]

            rt_changed = abs(rt_value - self.rt_previous) > 5
            lt_changed = abs(lt_value - self.lt_previous) > 5

            if rt_changed or lt_changed or rt_value == 255 or lt_value == 255:
                self.rt_previous = rt_value
                self.lt_previous = lt_value

                rt_normalized = rt_value / 255.0
                lt_normalized = lt_value / 255.0

                if rt_normalized > 0.1 and rt_normalized > lt_normalized:
                    self._move_robot(0.0, 0.0, -self.turn_speed)
                elif lt_normalized > 0.1 and lt_normalized > rt_normalized:
                    self._move_robot(0.0, 0.0, self.turn_speed)
                elif rt_normalized <= 0.1 and lt_normalized <= 0.1:
                    self._move_robot(0.0, 0.0)

            d_pad_value = data[13]

            if d_pad_value != self.d_pad_previous:
                self.d_pad_previous = d_pad_value

                if d_pad_value == 1:  # Up
                    self._move_robot(self.move_speed, 0.0)
                elif d_pad_value == 5:  # Down
                    self._move_robot(-self.move_speed, 0.0)
                elif d_pad_value == 7:  # Left
                    self._move_robot(0.0, self.move_speed)
                elif d_pad_value == 3:  # Right
                    self._move_robot(0.0, -self.move_speed)
                elif d_pad_value == 0:  # Nothing pressed
                    self._move_robot(0.0, 0.0)

        time.sleep(0.1)
