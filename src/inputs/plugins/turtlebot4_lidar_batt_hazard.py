import asyncio
import logging
import time
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import zenoh
from numpy import array
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

from inputs.base import SensorConfig
from inputs.base.loop import FuserInput
from providers.io_provider import IOProvider
from zenoh_idl import sensor_msgs


@dataclass
class Message:
    timestamp: float
    message: str


g_battery = None
g_lidar = None
g_hazard = None
intensity_treshold = 1
# values from the sensor are either 0 or 47
# so any value bewtween 1 and 47 works

vectorM2 = np.zeros(1080)
vectorM1 = np.zeros(1080)


def listenerBattery(sample):
    battery = sensor_msgs.BatteryState.deserialize(sample.payload.to_bytes())
    battery_percent = int(battery.percentage * 100)
    # print(f"Battery Percentage {battery_percent}")
    global g_battery
    if battery_percent < 5:
        g_battery = "CRITICAL: your battery is almost empty. Immediately move to your charging station and recharge."
    elif battery_percent < 15:
        g_battery = "Caution: your battery is running low. Consider finding your charging station and recharging."
    else:
        g_battery = None


def listenerHazard(sample):
    hazard = sensor_msgs.HazardDetectionVector.deserialize(sample.payload.to_bytes())
    global g_hazard
    if hazard.detections and len(hazard.detections) > 0:
        # print(f"Hazard Detections {hazard.detections}")
        for haz in hazard.detections:
            # print(f"Hazard Type:{haz.type} direction:{haz.header.frame_id}")
            if haz.type == 1:
                if haz.header.frame_id == "bump_front_right":
                    g_hazard = "DANGER: you are hitting something on your front right."
                    # if this hazard exists, report it immediately, and don't overwrite
                    # g_hazard with less important information
                    return
                if haz.header.frame_id == "bump_front_left":
                    g_hazard = "DANGER: you are hitting something on your front left."
                    return
                if haz.header.frame_id == "bump_front_center":
                    g_hazard = (
                        "DANGER: you are hitting something right in front of you."
                    )
                    return


def listenerScan(sample):
    scan = sensor_msgs.LaserScan.deserialize(sample.payload.to_bytes())
    clusters = []

    # smoothing
    global vectorM1, vectorM2
    # Add the new data, with the last two data vectros
    # then divide by 3 -> simple averaging
    smv = np.add(scan.ranges, vectorM1)
    smv = np.add(smv, vectorM2)
    smv = np.divide(smv, 3)
    vectorM2 = vectorM1
    vectorM1 = scan.ranges

    for distance, intensity in list(zip(smv, scan.intensities)):
        # print("distance (m):", distance)
        # print("intensity:", intensity)
        # print("angle:", angle)
        # let's look only at close things (< 0.50m)
        if distance <= 0.50:
            if intensity >= intensity_treshold:
                # convert to cm and flip to emphasize near returns
                clusters.append(51 - int(distance * 100))
            else:
                clusters.append(0)
        else:
            clusters.append(0)

    a = array(clusters)
    # roll the data so the "nose" of the robot is in the middle (around 530)
    a = np.roll(a, 278)
    # flip so we are in the human/robot frame
    a = a[::-1]
    # smooth a bit
    x_kde = gaussian_filter1d(a, 5)
    x_kde = x_kde[200:880]  # chop off data from the back of the robot
    peaks, _ = find_peaks(x_kde, height=0)

    max_x_peak = -10  # arbitrary negative number
    max_y_peak = -10
    for x in peaks:
        y = x_kde[int(x)]
        if y > max_y_peak:
            max_y_peak = y
            max_x_peak = int(x)

    # the array has length 680
    global g_lidar
    proximity = "close to"
    direction = "on your left"
    if max_x_peak > 0:
        if max_y_peak > 20:
            proximity = "hitting"
        if max_x_peak > 453:
            direction = "on your right"
        elif max_x_peak > 227:
            direction = "in front of you"
        g_lidar = f"CAUTION: You are {proximity} something {direction}."
    else:
        g_lidar = None


class TurtleBot4BattLIDARBump(FuserInput[str]):
    """
    TurtleBot4 LIDAR, Battery, and bump inputs.

    Takes specific TurtleBot4 ROS2/Zenoh messages, converts them to
    text strings, and sends them to the fuser.

    Maintains a buffer of processed messages.
    """

    def __init__(self, config: SensorConfig = SensorConfig()):
        super().__init__(config)

        # Track IO
        self.io_provider = IOProvider()

        # Buffer for storing the final output
        self.messages: list[Message] = []

        logging.info("Opening Zenoh TurtleBot4 session...")
        conf = zenoh.Config()
        self.z = zenoh.open(conf)

        logging.info(f"Config: {self.config}")

        self.URID = getattr(self.config, "URID", "default")
        logging.info(f"Using TurtleBot4 URID: {self.URID}")

        logging.info("Creating Zenoh TurtleBot4 Subscribers")
        self.scans = self.z.declare_subscriber(f"{self.URID}/pi/scan", listenerScan)
        self.batts = self.z.declare_subscriber(
            f"{self.URID}/c3/battery_state", listenerBattery
        )
        self.bump = self.z.declare_subscriber(
            f"{self.URID}/c3/hazard_detection", listenerHazard
        )

        # Simple description of sensor output to help LLM understand its importance and utility
        self.descriptor_for_LLM = "Body State"

    async def _poll(self) -> List[str]:
        """
        Poll for new state data.

        Returns
        -------
        List[str]
        """

        # Does the complexity of this seem confusing and kinda pointless to you?
        # It's on our radar and your patience is appreciated
        await asyncio.sleep(2.0)

        logging.info(f"TB4 batt:{g_battery} lidar:{g_lidar} hazard:{g_hazard}")

        return [g_battery, g_lidar, g_hazard]

    async def _raw_to_text(self, raw_input: List[str]) -> Optional[Message]:
        """
        Process raw lowstate to generate text description.

        Parameters
        ----------
        raw_input : List[str]
            State data to be processed

        Returns
        -------
        Message
            Timestamped message containing description
        """
        battery = raw_input[0]
        lidar = raw_input[1]
        hazard = raw_input[2]

        if hazard:
            message = hazard
            return Message(timestamp=time.time(), message=message)
        # when there is a hazard, that ALWAYS takes precendence
        # so we want the above to return
        # and we do not care about lidar etc
        if lidar:
            message = lidar
            return Message(timestamp=time.time(), message=message)

        if battery:
            message = battery
            return Message(timestamp=time.time(), message=message)

    async def raw_to_text(self, raw_input: List[float]):
        """
        Convert raw lowstate to text and update message buffer.

        Parameters
        ----------
        raw_input : List[float]
            Raw lowstate data to be processed
        """
        pending_message = await self._raw_to_text(raw_input)

        if pending_message is not None:
            self.messages.append(pending_message)

    def formatted_latest_buffer(self) -> Optional[str]:
        """
        Format and clear the latest buffer contents.

        Formats the most recent message with timestamp and class name,
        adds it to the IO provider, then clears the buffer.

        Returns
        -------
        Optional[str]
            Formatted string of buffer contents or None if buffer is empty
        """
        if len(self.messages) == 0:
            return None

        latest_message = self.messages[-1]

        result = f"""
{self.descriptor_for_LLM} INPUT
// START
{latest_message.message}
// END
"""

        # self.io_provider.add_input(
        #     self.__class__.__name__, latest_message.message, latest_message.timestamp
        # )
        self.messages = []

        global g_hazard
        g_hazard = None

        return result
