import asyncio
import logging
import time
from dataclasses import dataclass
from typing import List, Optional

from inputs.base import SensorConfig
from inputs.base.loop import FuserInput
from providers.io_provider import IOProvider

try:
    from unitree.unitree_sdk2py.core.channel import ChannelSubscriber
    from unitree.unitree_sdk2py.idl.unitree_hg.msg.dds_ import BmsState_, LowState_
except ImportError:
    logging.warning(
        "Unitree SDK not found. Please install the Unitree SDK to use this plugin."
    )
    LowState_ = None
    BmsState_ = None
    ChannelSubscriber = None


@dataclass
class Message:
    timestamp: float
    message: str


"""
class BmsState_(idl.IdlStruct, typename="unitree_hg.msg.dds_.BmsState_"):
    version_high: types.uint8
    version_low: types.uint8
    fn: types.uint8
    cell_vol: types.array[types.uint16, 40]
    bmsvoltage: types.array[types.uint32, 3]
    current: types.int32
    soc: types.uint8
    soh: types.uint8
    temperature: types.array[types.int16, 12]
    cycle: types.uint16
    manufacturer_date: types.uint16
    bmsstate: types.array[types.uint32, 5]
    reserve: types.array[types.uint32, 3]

class LowState_(idl.IdlStruct, typename="unitree_hg.msg.dds_.LowState_"):
    version: types.array[types.uint32, 2]
    mode_pr: types.uint8
    mode_machine: types.uint8
    tick: types.uint32
    imu_state: 'unitree.unitree_sdk2py.idl.unitree_hg.msg.dds_.IMUState_'
    motor_state: types.array['unitree.unitree_sdk2py.idl.unitree_hg.msg.dds_.MotorState_', 35]
    wireless_remote: types.array[types.uint8, 40]
"""


class UnitreeG1Basic(FuserInput[str]):
    """
    Unitree G1 Basic Functionality.

    Takes specific Unitree CycloneDDS Lowstate messages, converts them to
    text strings, and sends them to the fuser.

    Processes Unitree Lowstate information.
    These are things like joint position and battery charge.

    Maintains a buffer of processed messages.
    """

    def __init__(self, config: SensorConfig = SensorConfig()):
        """
        Initialize Unitree bridge with empty message buffer.
        """
        super().__init__(config)

        # Track IO
        self.io_provider = IOProvider()

        # Messages buffer
        self.messages: list[Message] = []

        # create subscriber
        self.low_state = None
        self.lowstate_subscriber = None
        self.bmsstate_subscriber = None

        unitree_ethernet = getattr(self.config, "unitree_ethernet", None)
        logging.info(f"UnitreeG1Basic using ethernet: {unitree_ethernet}")

        # Joint angles e.g.
        if unitree_ethernet and unitree_ethernet != "":
            # only set up if we are connected to a robot
            self.lowstate_subscriber = ChannelSubscriber("rt/lowstate", LowState_)
            self.lowstate_subscriber.Init(self.LowStateHandler, 10)

            # Battery specific data
            self.bmsstate_subscriber = ChannelSubscriber("rt/lf/bmsstate", BmsState_)
            self.bmsstate_subscriber.Init(self.BMSStateHandler, 10)

        self.latest_v = 0.0
        self.latest_a = 0.0

        self.g1_lowbatt_percent = 20.0  # percent
        self.descriptor_for_LLM = "Energy Level"

    def BMSStateHandler(self, msg: BmsState_):
        self.bms_state = msg
        logging.debug(f"BmsState_: {msg}")

        self.latest_v = float(msg.bmsvoltage[0])
        self.latest_a = float(msg.current)

    def LowStateHandler(self, msg: LowState_):
        self.low_state = msg
        logging.debug(f"LowState_: {msg}")

    async def _poll(self) -> List[float]:
        """
        Poll for new lowstate data.

        Returns
        -------
        List[float]
            list of floats
        """

        await asyncio.sleep(2.0)

        # logging.info(f"Battery voltage: {self.latest_v} current: {self.latest_a}")

        return [self.latest_v, self.latest_a]

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
        battery_voltage = raw_input[0]

        diff = battery_voltage - 43600
        battery_percent = 0.00

        if diff > 0:
            battery_percent = round(diff / 96.9, 2)

        logging.info(
            f"Battery:{self.latest_v}mV, {self.latest_a}mA, percent:{battery_percent}"
        )

        if battery_percent < self.g1_lowbatt_percent:
            message = "WARNING: You are low on energy. SIT DOWN NOW."
            return Message(timestamp=time.time(), message=message)
        elif (
            battery_percent < self.g1_lowbatt_percent + 10.0
        ):  # the +10% is an emergency reserve
            message = "WARNING: You are low on energy. Consider sitting down."
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

        self.io_provider.add_input(
            self.descriptor_for_LLM, latest_message.message, latest_message.timestamp
        )
        self.messages = []

        return result
