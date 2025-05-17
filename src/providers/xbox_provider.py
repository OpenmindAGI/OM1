import logging
import threading
import time
from typing import Optional

from .singleton import singleton

try:
    import hid
except ImportError:
    logging.warning(
        "HID library not found. Please install the HIDAPI library to use this plugin."
    )
    hid = None


@singleton
class XboxProvider:

    def __init__(
        self,
        wait: bool = False,
    ):
        logging.info("Booting XBox Provider")

        if wait:
            # no need to reinit driver
            return

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

        # Software Debounce
        self.rt_previous = 0
        self.lt_previous = 0
        self.d_pad_previous = 0
        self.button_previous = 0

        self._xbox: Optional[str] = None

        self.running = False
        self._thread: Optional[threading.Thread] = None
        self.start()

    def xboxProcessor(self, data):

        if len(data) > 0:

            # logging.info(f"Xbox data: {data}")
            self._xbox = None

            # Process triggers for rotation
            # RT is typically on byte 9, LT on byte 8 for Xbox controllers
            rt_value = data[11]  # Right Trigger
            lt_value = data[9]  # Left Trigger
            d_pad_value = data[13]
            button_value = data[14]

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

                # Right Trigger - clockwise rotation
                if rt_normalized > 0.8 and rt_normalized > lt_normalized:
                    self._xbox = "move_robot(0.0, 0.0, -turn_speed)"
                # Left Trigger - counter-clockwise rotation
                elif lt_normalized > 0.8 and lt_normalized > rt_normalized:
                    self._xbox = "move_robot(0.0, 0.0, turn_speed)"
                # Both triggers released or below threshold
                elif rt_normalized <= 0.8 and lt_normalized <= 0.8:
                    self._xbox = "move_robot(0.0, 0.0, 0.0)"
                    logging.debug("Triggers released - Stopping rotation")

                self.button_previous = button_value
                return

            if d_pad_value != self.d_pad_previous:

                self.d_pad_previous = d_pad_value

                # Control robot movement based on D-pad
                if d_pad_value == 1:  # Up
                    logging.info("D-pad UP - Moving forward")
                    self._xbox = "move_robot(move_speed, 0.0, 0.0)"
                elif d_pad_value == 5:  # Down
                    logging.info("D-pad DOWN - Moving backward")
                    self._xbox = "move_robot(-move_speed, 0.0, 0.0)"
                elif d_pad_value == 7:  # Left
                    logging.info("D-pad LEFT - Turning left")
                    self._xbox = "move_robot(0.0, move_speed, 0.0)"
                elif d_pad_value == 3:  # Right
                    logging.info("D-pad RIGHT - Turning right")
                    self._xbox = "move_robot(0.0, -move_speed, 0.0)"
                elif d_pad_value == 0:  # Nothing pressed
                    logging.debug("D-pad released - Stopping movement")
                    self._xbox = "move_robot(0.0, 0.0, 0.0)"

                self.button_previous = button_value
                return

            if self.button_previous == 0 and button_value > 0:
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
                    self._xbox = "sport(stand_up)"
                # button B
                elif button_value == 2:
                    logging.info("Controller unitree: lay_down")
                    self._xbox = "sport(lay_down)"
                # X button
                elif button_value == 8:
                    logging.info("Controller unitree: say_hello")
                    self._xbox = "sport(say_hello)"
                # Y button
                elif button_value == 16:
                    logging.info("Controller unitree: stretch")
                    self._xbox = "sport(stretch)"

                logging.info(f"Gamepad button depressed edge {button_value}")
                self.button_previous = button_value

            # refresh the button value for debounce
            self.button_previous = button_value

    def start(self):
        """
        Starts the Navigation Provider and processing thread
        if not already running.
        """
        if self._thread and self._thread.is_alive():
            return

        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        """
        Main loop for the Xbox provider.
        """
        while self.running:

            # logging.info(f"Xbox tick")
            data = None

            if self.gamepad:
                # try to read USB data, and if there is nothing there,
                # timeout
                # data = list(self.gamepad.read(64, timeout=50))
                data = list(self.gamepad.read(64, timeout=50))
                if len(data) > 0:
                    self.xboxProcessor(data)
                else:
                    self._xbox = None

            time.sleep(0.1)

    def stop(self):
        """
        Stop the provider.
        """
        self.running = False
        if self._thread:
            logging.info("Stopping Xbox provider")
            self._thread.join(timeout=5)

    @property
    def xbox(self) -> Optional[str]:
        # """
        # Get the current controller input
        # """
        return self._xbox
