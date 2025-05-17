import asyncio
import logging
import time
from dataclasses import dataclass
from typing import List, Optional

from inputs.base import SensorConfig
from inputs.base.loop import FuserInput
from providers import BatteryStatus, IOProvider, StatusProvider, TeleopsStatus

try:
    from unitree.unitree_sdk2py.core.channel import ChannelSubscriber
    from unitree.unitree_sdk2py.idl.geometry_msgs.msg.dds_ import PoseStamped_
    from unitree.unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_
except ImportError:
    logging.warning(
        "Unitree SDK not found. Please install the Unitree SDK to use this plugin."
    )

    class ChannelSubscriber:
        def __init__(self):
            pass

    class PoseStamped_:
        def __init__(self):
            pass

    class LowState_:
        def __init__(self):
            pass

    class BmsState_:
        def __init__(self):
            pass


@dataclass
class Message:
    timestamp: float
    message: str


class UnitreeGo2Lowstate(FuserInput[str]):
    """
    Unitree Go2 Air Lowstate bridge.

    Takes specific Unitree CycloneDDS Lowstate messages, converts them to
    text strings, and sends them to the fuser.

    Processes Unitree Lowstate information. These are things like joint position and battery charge.

    Maintains a buffer of processed messages.
    """

    def __init__(self, config: SensorConfig = SensorConfig()):
        """
        Initialize Unitree bridge with empty message buffer.
        """
        super().__init__(config)

        api_key = getattr(self.config, "api_key", None)

        # IO provider
        self.io_provider = IOProvider()

        # Status provider
        self.status_provider = StatusProvider(api_key=api_key)

        # Messages buffer
        self.messages: list[Message] = []

        # create subscriber
        self.low_state = None
        self.lowstate_subscriber = None

        self.lowstate_subscriber = ChannelSubscriber("rt/lowstate", LowState_)
        self.lowstate_subscriber.Init(self.LowStateMessageHandler, 10)

        self.pose_subscriber = ChannelSubscriber("rt/utlidar/robot_pose", PoseStamped_)
        self.pose_subscriber.Init(self.PoseMessageHandler, 10)

        # battery state
        self.battery_percentage = 0.0
        self.battery_voltage = 0.0
        self.battery_amperes = 0.0
        self.battery_temperature = 0

        self.body_height = 0
        self.body_attitude_previous = None

        # Simple description of sensor output to help LLM understand its importance and utility
        self.descriptor_for_LLM = "Body State"

    def LowStateMessageHandler(self, msg: LowState_):
        self.low_state = msg

        self.battery_percentage = float(msg.bms_state.soc)
        self.battery_voltage = float(msg.power_v)
        self.battery_amperes = float(msg.power_a)
        self.battery_temperature = int(
            (msg.temperature_ntc1 + msg.temperature_ntc2) / 2
        )

        # other things you can read
        # print("FR_0 motor state: ", msg.motor_state[go2.LegID["FR_0"]])
        # print("IMU state: ", msg.imu_state)
        # print("Battery state: voltage: ", msg.power_v, "current: ", msg.power_a)

    def PoseMessageHandler(self, msg: PoseStamped_):
        self.pose = msg
        self.body_height = int(self.pose.pose.position.z * 100)

        if self.body_attitude_previous is None:
            if self.body_height < 24:
                self.body_attitude_previous = "sitting"
            else:
                self.body_attitude_previous = "standing"

    async def update_status(self):
        """
        Report the battery status to the status provider.
        """
        self.status_provider.share_status(
            TeleopsStatus(
                machine_name="UnitreeGo2",
                update_time=time.time(),
                battery_status=BatteryStatus(
                    battery_level=self.battery_percentage,
                    temperature=self.battery_temperature,
                    voltage=self.battery_voltage,
                    timestamp=time.time(),
                    charging_status=False,
                ),
            )
        )

    async def _poll(self) -> List[float]:
        """
        Poll for new lowstate data.

        Returns
        -------
        List[float]
            list of floats
        """

        # Does the complexity of this seem confusing and kinda pointless to you?
        # It's on our radar and your patience is appreciated
        await asyncio.sleep(2.0)

        await self.update_status()

        logging.info(
            f"Battery percentage: {self.battery_percentage} voltage: {self.battery_voltage} amperes: {self.battery_amperes} attitude: {self.body_height}"
        )

        return [
            self.battery_percentage,
            self.battery_voltage,
            self.battery_amperes,
            self.body_height,
        ]

    async def _raw_to_text(self, raw_input: List[float]) -> Optional[Message]:
        """
        Process raw lowstate to generate text description.

        Parameters
        ----------
        raw_input : List[float]
            Raw lowstate data to be processed

        Returns
        -------
        Message
            Timestamped message containing description
        """

        battery_percentage = raw_input[0]
        height = raw_input[3]
        logging.info(f"Battery percentage: {battery_percentage} height: {height}")

        if battery_percentage < 15:
            message = "WARNING: You are low on energy. SIT DOWN NOW."
            return Message(timestamp=time.time(), message=message)

        # when there is a battery issue, that ALWAYS takes precendence
        # so we want the above to return
        # and we do not care about body height
        if height < 24 and self.body_attitude_previous == "standing":
            message = "You just sat down."
            self.body_attitude_previous == "sitting"
            logging.info("You just sat down")
            return Message(timestamp=time.time(), message=message)
        elif height >= 24 and self.body_attitude_previous == "sitting":
            message = "You just stood up."
            self.body_attitude_previous == "standing"
            logging.info("You just stood up")
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
INPUT: {self.descriptor_for_LLM}
// START
{latest_message.message}
// END
"""

        self.io_provider.add_input(
            self.__class__.__name__, latest_message.message, latest_message.timestamp
        )
        self.messages = []

        return result
