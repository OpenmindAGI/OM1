import logging
import math
from actions.base import ActionConnector, ActionConfig
from providers.io_provider import IOProvider
from .interface import MoveToPeerAction, MoveToPeerInput


class MoveToPeerRos2Connector(ActionConnector[MoveToPeerInput]):
    def __init__(self, config: ActionConfig):
        super().__init__(config)
        self.io = IOProvider()
        # init sport client as before…
        from unitree.unitree_sdk2py.go2.sport.sport_client import SportClient

        self.sport_client = SportClient()
        self.sport_client.SetTimeout(10.0)
        self.sport_client.Init()

    async def connect(self, input_protocol: MoveToPeerInput) -> None:
        # check desired action
        if input_protocol.action == MoveToPeerAction.IDLE:
            logging.info("MoveToPeer: idle, no movement commanded.")
            return

        # else NAVIGATE
        lat0 = float(self.io.get_dynamic_variable("latitude") or 0)
        lon0 = float(self.io.get_dynamic_variable("longitude") or 0)
        lat1 = float(self.io.get_dynamic_variable("closest_peer_lat") or 0)
        lon1 = float(self.io.get_dynamic_variable("closest_peer_lon") or 0)

        # compute approximate bearing vector in meters
        R = 6371000
        dlat = math.radians(lat1 - lat0)
        dlon = math.radians(lon1 - lon0)
        x = dlon * math.cos(math.radians((lat0 + lat1) / 2)) * R
        y = dlat * R
        norm = math.hypot(x, y) or 1
        vx = (y / norm) * 0.5
        vy = (x / norm) * 0.5

        logging.info(
            f"MoveToPeer: moving → Δx={x:.1f}m Δy={y:.1f}m  vx={vx:.2f}, vy={vy:.2f}"
        )
        self.sport_client.Move(vx, vy, 0.0)
