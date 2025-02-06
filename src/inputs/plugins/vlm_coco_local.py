import asyncio
import collections
import logging
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np
import torch
from PIL import Image
from torchvision.models import detection as detection_model

from inputs.base import SensorOutputConfig
from inputs.base.loop import FuserInput
from providers.io_provider import IOProvider

Detection = collections.namedtuple("Detection", "label, bbox, score")


@dataclass
class Message:
    """
    Container for timestamped messages.

    Parameters
    ----------
    timestamp : float
        Unix timestamp of the message
    message : str
        Content of the message
    """

    timestamp: float
    message: str


def check_webcam():
    """
    Checks if a webcam is available and returns True if found, False otherwise.
    """
    cap = cv2.VideoCapture(0)  # 0 is the default camera index
    if not cap.isOpened():
        logging.info("No webcam found")
        return False
    logging.info("Found cam(0)")
    return True


class VLM_COCO_Local(FuserInput[Image.Image]):
    """
    Detects COCO objects in image and publishes messages.
    Uses PyTorch and FasterRCNN_MobileNet model from torchvision.
    Bounding Boxes use image convention, ie center.y = 0 means top of image.
    """

    def __init__(self, config: SensorOutputConfig = SensorOutputConfig()):
        """
        Initialize VLM input handler with empty message buffer.
        """
        super().__init__(config)

        self.device = "cpu"
        self.detection_threshold = 0.9

        # Track IO
        self.io_provider = IOProvider()

        # Messages buffer
        self.messages: list[Message] = []

        self.descriptor_for_LLM = "COCO Object Detector"

        # Low resolution Faster R-CNN model with a MobileNetV3-Large backbone tuned for mobile use cases.
        self.model = detection_model.fasterrcnn_mobilenet_v3_large_320_fpn(
            weights="FasterRCNN_MobileNet_V3_Large_320_FPN_Weights.COCO_V1",
            progress=True,
            weights_backbone="MobileNet_V3_Large_Weights.IMAGENET1K_V1",
        ).to(self.device)
        self.class_labels = (
            detection_model.FasterRCNN_MobileNet_V3_Large_320_FPN_Weights.DEFAULT.meta[
                "categories"
            ]
        )
        self.model.eval()
        logging.info("COCO Object Detector Started")

        self.have_cam = check_webcam()

        # Start capturing video, if we have a webcam
        self.cap = None
        if self.have_cam:
            self.cap = cv2.VideoCapture(0)

    async def _poll(self) -> Image.Image:
        """
        Poll for new image input.

        Currently generates random colored images for testing.
        In production, this would interface with camera or sensor.

        Returns
        -------
        Image.Image
            Generated or captured image
        """
        await asyncio.sleep(0.5)

        # Capture a frame every 500 ms
        if self.have_cam:
            ret, frame = self.cap.read()
            return frame

    async def _raw_to_text(self, raw_input: Image.Image) -> Optional[Message]:
        """
        Process raw image input to generate text description.

        Parameters
        ----------
        raw_input : Image.Image
            Input image to process

        Returns
        -------
        Message
            Timestamped message containing description
        """

        filtered_detections = None

        if raw_input:
            image = raw_input.copy().transpose((2, 0, 1))
            batch_image = np.expand_dims(image, axis=0)
            tensor_image = torch.tensor(
                batch_image / 255.0, dtype=torch.float, device=self.device
            )
            mobilenet_detections = self.model(tensor_image)[
                0
            ]  # pylint: disable=E1102 disable not callable warning
            filtered_detections = [
                Detection(label_id, box, score)
                for label_id, box, score in zip(
                    mobilenet_detections["labels"],
                    mobilenet_detections["boxes"],
                    mobilenet_detections["scores"],
                )
                if score >= self.detection_threshold
            ]
            logging.debug(f"filtered_detections {filtered_detections}")

        sentence = None

        if len(filtered_detections) > 0:
            pred_boxes = torch.stack(
                [detection.bbox for detection in filtered_detections]
            )
            pred_labels = [
                self.class_labels[detection.label] for detection in filtered_detections
            ]

            thing = pred_labels[0]
            # Calculate center coordinates of first object
            x1 = pred_boxes[0, 0]
            # y1 = pred_boxes[0, 1]
            x2 = pred_boxes[0, 2]
            # y2 = pred_boxes[0, 3]
            center_x = (x1 + x2) / 2
            # center_y = (y1 + y2) / 2

            direction = "in front of you."
            if center_x < 480:
                direction = "on your left."
            elif center_x > 960:
                direction = "on your right."

            sentence = f"You see a {thing} {direction}"
            logging.info(f"VLM_COCO_Local: {sentence}")

        if sentence is not None:
            return Message(timestamp=time.time(), message=sentence)

    async def raw_to_text(self, raw_input: Image.Image):
        """
        Convert raw image to text and update message buffer.

        Parameters
        ----------
        raw_input : Image.Image
            Raw image to be processed
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
            self.__class__.__name__, latest_message.message, latest_message.timestamp
        )
        self.messages = []

        return result
