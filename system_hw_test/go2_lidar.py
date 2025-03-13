import sys
import time

from unitree.unitree_sdk2py.core.channel import (
    ChannelFactoryInitialize,
    ChannelSubscriber,
)
from unitree.unitree_sdk2py.idl.sensor_msgs.msg.dds_ import PointCloud2_


class Custom:
    def __init__(self):
        self.low_state = None

    # Public methods
    def Init(self):
        # create subscriber #
        self.subscriber = ChannelSubscriber("rt/utlidar/cloud", PointCloud2_)
        self.subscriber.Init(self.MessageHandler, 10)

    def MessageHandler(self, msg: PointCloud2_):
        self.cloud = msg
        print("Cloud: ", msg)


if __name__ == "__main__":

    if len(sys.argv) > 1:
        ChannelFactoryInitialize(0, sys.argv[1])
    else:
        ChannelFactoryInitialize(0)

    custom = Custom()
    custom.Init()

    while True:
        time.sleep(1)
