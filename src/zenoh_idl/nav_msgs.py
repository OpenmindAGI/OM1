from dataclasses import dataclass

from pycdr2 import IdlStruct

from .geometry_msgs import PoseWithCovariance, TwistWithCovariance
from .std_msgs import Header, String


@dataclass
class Odometry(IdlStruct, typename="Odometry"):
    header: Header
    child_frame_id: String
    pose: PoseWithCovariance
    twist: TwistWithCovariance
