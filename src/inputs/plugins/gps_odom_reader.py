#!/usr/bin/env python3
"""
Light-weight odometry reader (Unitree DDS).
"""

from __future__ import annotations

import asyncio
import math
import logging
import time
from dataclasses import dataclass
from typing import Optional

from inputs.base import SensorConfig
from inputs.base.loop import FuserInput
from providers.io_provider import IOProvider

# ── Cyclone DDS ────────────────────────────────────────────────────────────
from unitree.unitree_sdk2py.core.channel import (
    ChannelSubscriber,
    ChannelFactoryInitialize,          # noqa: F401 – created elsewhere
)
from unitree.unitree_sdk2py.idl.unitree_go.msg.dds_ import SportModeState_

# ─── constants ─────────────────────────────────────────────────────────────
R_EARTH = 6_371_000.0        # mean Earth radius (m)


# ── buffer helper ─────────────────────────────────────────────────────────
@dataclass
class Message:
    """
    Container for timestamped messages.

    Parameters
    ----------
    timestamp : float
        Unix timestamp of the message
    text : str
        Content of the message
    """

    timestamp: float
    text: str


# ── main reader class ──────────────────────────────────────────────────────
class GPSOdomReader(FuserInput[str]):
    """
    Maintains global pose (lat, lon, yaw) from Unitree Sport-mode state.
    """

    # ── init ─────────────────────────────────────────────────────────────
    def __init__(self, config: SensorConfig = SensorConfig()):
        super().__init__(config)

        # --- origin (deg) ------------------------------------------------
        self.lat0: float | None = getattr(config, "origin_lat", None)
        self.lon0: float | None = getattr(config, "origin_lon", None)
        if self.lat0 is None or self.lon0 is None:
            raise ValueError("origin_lat and origin_lon must be provided")

        yaw0_deg = getattr(config, "origin_yaw_deg", None)
        self._yaw_offset = math.radians(yaw0_deg) if yaw0_deg is not None else 0.0

        # --- current pose -----------------------------------------------
        self.pose_x = 0.0   # metres East  of origin
        self.pose_y = 0.0   # metres North of origin
        self.pose_yaw = 0.0 # rad

        # --- DDS subscription -------------------------------------------
        self.last_odom: SportModeState_ | None = None
        self.odom_sub = ChannelSubscriber("rt/sportmodestate", SportModeState_)
        self.odom_sub.Init(self._odom_cb, 10)

        # --- I/O + buffer ------------------------------------------------
        self.io_provider = IOProvider()
        self.buf: list[Message] = []
        self.descriptor_for_LLM = "Location and Velocity"

    # ── helpers ──────────────────────────────────────────────────────────
    @staticmethod
    def _wrap_angle(a: float) -> float:
        return (a + math.pi) % (2 * math.pi) - math.pi

    def _xy_to_latlon(self, x: float, y: float):
        φ0, λ0 = map(math.radians, (self.lat0, self.lon0))
        φ = φ0 + y / R_EARTH
        λ = λ0 + x / (R_EARTH * math.cos(φ0))
        return map(math.degrees, (φ, λ))

    # ── DDS callback ─────────────────────────────────────────────────────
    def _odom_cb(self, msg: SportModeState_):
        self.last_odom = msg

    # ── pose update step ────────────────────────────────────────────────
    async def _update_pose(self):
        if not self.last_odom:
            return

        # translation
        self.pose_x, self.pose_y = self.last_odom.position[0:2]

        # orientation
        yaw_world = self.last_odom.imu_state.rpy[2]
        self.pose_yaw = self._wrap_angle(yaw_world - self._yaw_offset)

        # publish through IOProvider
        lat, lon = self._xy_to_latlon(self.pose_x, self.pose_y)
        self.io_provider.add_dynamic_variable("latitude",  lat)
        self.io_provider.add_dynamic_variable("longitude", lon)
        self.io_provider.add_dynamic_variable("yaw_deg",       math.degrees(self.pose_yaw))

    # ── polling loop (FuserInput interface) ─────────────────────────────
    async def _poll(self) -> Optional[str]:
        await asyncio.sleep(0.5)
        await self._update_pose()
        return None

    # ---------------------------------------------------------------------
    # ChatGPT-bridge helpers — minimal but functional
    # ---------------------------------------------------------------------
    async def raw_to_text(self, raw: str):
        """
        Allow external callers (e.g. GUI, CLI) to push arbitrary text into
        the same IO/logging path that serial parsing used to feed.
        """
        if not raw:
            return
        now  = time.time()
        text = raw.strip()
        self.buf.append(Message(now, text))
        self.io_provider.add_input(self.__class__.__name__, text, now)

    def formatted_latest_buffer(self) -> Optional[str]:
        """
        Return the newest buffered message in the canonical // START … // END
        block that the LLM side expects, then clear the buffer.
        """
        if not self.buf:
            return None
        m = self.buf[-1]
        self.buf.clear()
        self.io_provider.add_input(self.__class__.__name__, m.text, m.timestamp)
        return f"""
{self.descriptor_for_LLM} INPUT
// START
{m.text}
// END
"""
