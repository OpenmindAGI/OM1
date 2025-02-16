import logging

from actions.base import ActionConfig, ActionConnector
from actions.face.interface import FaceInput


class FaceRos2Connector(ActionConnector[FaceInput]):

    def __init__(self, config: ActionConfig):
        super().__init__(config)

    async def connect(self, output_interface: FaceInput) -> None:
        # define/clarify the datatype
        new_msg = {"face": ""}

        if output_interface.action == "smile":
            new_msg["face"] = "smile"
        elif output_interface.action == "frown":
            new_msg["face"] = "frown"
        elif output_interface.action == "cry":
            new_msg["face"] = "cry"
        elif output_interface.action == "think":
            new_msg["face"] = "think"
        elif output_interface.action == "joy":
            new_msg["face"] = "joy"
        else:
            logging.info(f"Unknown face type: {output_interface.action}")
            # raise ValueError(f"Unknown face type: {output_interface.action}")

        logging.info(f"SendThisToROS2: {new_msg}")
