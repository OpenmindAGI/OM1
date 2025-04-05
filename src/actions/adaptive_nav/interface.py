from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Tuple

from actions.base import Interface


class NavigationMode(str, Enum):
    """Navigation modes for the adaptive navigation system"""
    SAFE = "safe"              # Prioritize safety, slow speed
    NORMAL = "normal"          # Balanced approach
    EFFICIENT = "efficient"    # Faster movement, more direct paths
    SOCIAL = "social"          # Consider human social norms (personal space)
    FOLLOW = "follow"          # Follow a person or object


@dataclass
class Point2D:
    """Simple 2D point class for navigation targets"""
    x: float
    y: float


@dataclass
class NavigationInput:
    """Input parameters for adaptive navigation"""
    mode: NavigationMode = NavigationMode.NORMAL
    target: Optional[Point2D] = None  # Target position
    avoid_radius: float = 0.5  # Radius to keep from obstacles (meters)
    max_speed: float = 0.5  # Maximum speed (m/s)
    path_timeout: float = 30.0  # Maximum time to attempt path (seconds)
    enable_dynamic_replanning: bool = True  # Re-plan if obstacles change


@dataclass
class NavigationOutput:
    """Output from adaptive navigation system"""
    success: bool = False
    message: str = ""
    path_points: List[Point2D] = None
    obstacles_detected: int = 0
    path_length: float = 0.0
    estimated_time: float = 0.0


@dataclass
class AdaptiveNav(Interface[NavigationInput, NavigationOutput]):
    """
    Adaptive navigation in complex environments.
    
    Enables robots to navigate through dynamic, human-populated spaces,
    with real-time obstacle avoidance and path adjustments.
    """
    input: NavigationInput
    output: NavigationOutput 