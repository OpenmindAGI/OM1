import json
import logging
import multiprocessing as mp
import time
from dataclasses import dataclass
from queue import Empty, Full
from typing import Optional

from runtime.logging import LoggingConfig, get_logging_config, setup_logging

try:
    from unitree.unitree_sdk2py.core.channel import ChannelFactoryInitialize
    from unitree.unitree_sdk2py.go2.sport.sport_client import SportClient
except ImportError:
    logging.error(
        "Unitree SDK or CycloneDDS not found. Please install the unitree_sdk2py package or CycloneDDS."
    )

from .singleton import singleton


@dataclass
class UnitreeGo2State:
    """
    Unitree Go2 State Data Class.

    This class holds the state data for the Unitree Go2 robot.
    """

    state: str
    body_height: float
    foot_raise_height: float
    speed_level: int
    gait: int
    dance: bool
    economic_gait: bool
    continuous_gait: bool
    timestamp: float


def unitree_go2_state_processor(
    channel: str,
    data_queue: mp.Queue,
    logging_config: Optional[LoggingConfig] = None,
) -> None:
    """
    Process function for the Unitree Go2 State Provider.

    This function runs in a separate process to periodically retrieve the state
    of the Unitree Go2 robot and put it into a multiprocessing queue.

    Parameters
    ----------
    channel : str
        The channel to connect to the Unitree Go2 robot.
    data_queue : mp.Queue
        Queue for sending the retrieved state data.
    logging_config : LoggingConfig, optional
        Optional logging configuration. If provided, it will override the default logging settings.
    """
    setup_logging("unitree_go2_state_processor", logging_config=logging_config)

    try:
        ChannelFactoryInitialize(0, channel)
    except Exception as e:
        logging.error(f"Error initializing Unitree Go2 channel: {e}")
        return

    try:
        sport_client = SportClient()
        sport_client.Init()
        sport_client.SetTimeout(10.0)
        logging.info("Unitree Go2 State Provider initialized successfully")
    except Exception as e:
        logging.error(f"Error initializing Unitree Go2 State Provider: {e}")
        return

    while True:
        try:
            state = sport_client.GetState(
                [
                    "state",
                    "bodyHeight",
                    "footRaiseHeight",
                    "speedLevel",
                    "gait",
                    "dance",
                    "economicGait",
                    "continuousGait",
                    "timestamp",
                ]
            )
            if state[0] != 0:
                logging.error(f"Failed to get state from Unitree Go2: {state[0]}")
                continue

            parsed_state = {
                key: json.loads(value)["data"] for key, value in state[1].items()
            }
            data = UnitreeGo2State(
                state=parsed_state["state"],
                body_height=parsed_state["bodyHeight"],
                foot_raise_height=parsed_state["footRaiseHeight"],
                speed_level=parsed_state["speedLevel"],
                gait=parsed_state["gait"],
                dance=parsed_state["dance"],
                economic_gait=parsed_state["economicGait"],
                continuous_gait=parsed_state["continuousGait"],
                timestamp=time.time(),
            )

            try:
                data_queue.put(data, timeout=0.1)
            except Full:
                try:
                    data_queue.get_nowait()
                    data_queue.put_nowait(data)
                except Empty:
                    # This is used to fix the race condition where the queue is empty by another process
                    try:
                        data_queue.put(data, timeout=0.1)
                    except Full:
                        logging.warning(
                            "Failed to update Unitree Go2 state queue - another process intervened"
                        )

        except Exception as e:
            logging.error(f"Error retrieving Unitree Go2 state: {e}")

        time.sleep(1.0)


@singleton
class UnitreeGo2StateProvider:
    """
    Unitree Go2 State Provider.

    This class implements a singleton pattern to manage:
        * Unitree Go2 state data using either Zenoh or CycloneDDS
    """

    def __init__(self):
        """
        Robot and sensor configuration
        """
        logging.info("Booting Unitree Go2 State Provider")

        self.channel = None

        self.data_queue: mp.Queue[UnitreeGo2State] = mp.Queue(maxsize=1)
        self._state_processor_thread: Optional[mp.Process] = None

        self.go2_state: Optional[UnitreeGo2State] = None

    def start(self, channel: str) -> None:
        """
        Start the Unitree Go2 State Provider.

        This method initializes the Unitree Go2 state provider and starts the
        state retrieval process.
        """
        if self._state_processor_thread and self._state_processor_thread.is_alive():
            logging.warning("Unitree Go2 State Provider is already running.")
            return

        if not channel:
            logging.error(
                "Channel must be specified to start the Unitree Go2 State Provider."
            )
            return

        self.channel = channel
        logging.info(f"Starting Unitree Go2 State Provider on channel: {channel}")

        self._state_processor_thread = mp.Process(
            target=unitree_go2_state_processor,
            args=(self.channel, self.data_queue, get_logging_config()),
            daemon=True,
        )
        self._state_processor_thread.start()

    @property
    def state(self, timeout: float = 1.0) -> Optional[str]:
        """
        Get the current state of the Unitree Go2 robot.

        Parameters
        ----------
        timeout : float
            The maximum time to wait for the state data to be available in the queue.

        Returns
        -------
        Optional[str]
            The current state of the Unitree Go2 robot, or None if no state is available.
        """
        # Return the cached state if it is within the last second
        if self.go2_state and self.go2_state.timestamp > time.time() - 1:
            return self.go2_state.state

        # Otherwise, try to get the state from the queue
        try:
            self.go2_state = self.data_queue.get(timeout=timeout)
            return self.go2_state.state
        except Empty:
            logging.warning("No Unitree Go2 state data available in the queue")
            return None
