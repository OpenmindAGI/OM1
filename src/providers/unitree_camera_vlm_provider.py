import base64
import logging
import threading
import time
from typing import Callable, Optional

import cv2
import numpy as np
from om1_utils import ws
from om1_vlm import VideoStream

from .singleton import singleton

try:
    from unitree.unitree_sdk2py.go2.video.video_client import VideoClient
except ImportError:
    logging.warning(
        "Unitree SDK not found. Please install the Unitree SDK to use this plugin."
    )
    VideoClient = None


# Resize target for video stream
TARGET_WIDTH = 640
TARGET_HEIGHT = 480


class UnitreeCameraVideoStream(VideoStream):
    """
    Video Stream class for Unitree Cameras.

    This class extends the VideoStream class to handle Unitree camera-specific
    video streaming and processing.
    """

    def __init__(self, frame_callback=None, fps=30):
        super().__init__(frame_callback, fps)

        self.video_client = VideoClient()
        self.video_client.Init()

    def on_video(self):
        """
        Main video capture and processing loop for Unitree cameras.

        Captures frames from the camera, encodes them to base64,
        and sends them through the callback if registered.
        """
        logging.info("Starting Unitree Camera Video Stream")
        while self.running:
            try:
                code, data = self.video_client.GetImageSample()

                if code == 0:
                    # Convert to numpy image
                    image_data = np.frombuffer(bytes(data), dtype=np.uint8)
                    image = cv2.imdecode(image_data, cv2.IMREAD_COLOR)

                    if image is not None:
                        # Calculate new dimensions maintaining aspect ratio
                        height, width = image.shape[:2]
                        ratio = width / height

                        if width > height:
                            new_width = TARGET_WIDTH
                            new_height = int(TARGET_WIDTH / ratio)
                        else:
                            new_height = TARGET_HEIGHT
                            new_width = int(TARGET_HEIGHT * ratio)

                        # Resize image
                        resized_image = cv2.resize(
                            image, (new_width, new_height), interpolation=cv2.INTER_AREA
                        )
                        _, buffer = cv2.imencode(
                            ".jpg", resized_image, [cv2.IMWRITE_JPEG_QUALITY, 70]
                        )
                        frame_data = base64.b64encode(buffer).decode("utf-8")

                        if self.frame_callback:
                            self.frame_callback(frame_data)
                    else:
                        logging.warning("Failed to decode image")
                else:
                    logging.error(f"Failed to get image sample, code: {code}")

                # Control frame rate
                time.sleep(self.frame_delay)

            except Exception as e:
                logging.error(f"Error in video processing loop: {e}")
                continue

        logging.info("Stopping Camera Video Stream")


@singleton
class UnitreeCameraVLMProvider:
    """
    VLM Provider that handles audio streaming and websocket communication.

     This class implements a singleton pattern to manage camera input streaming and websocket
     communication for vlm services. It runs in a separate thread to handle
     continuous vlm processing.

     Parameters
     ----------
     ws_url : str
         The websocket URL for the VLM service connection.
     fps : int
         Frames per second for the video stream.
    """

    def __init__(self, ws_url: str, fps: int = 5):
        """
        Initialize the VLM Provider.

        Parameters
        ----------
        ws_url : str
            The websocket URL for the VLM service connection.
        """
        self.running: bool = False
        self.ws_client: ws.Client = ws.Client(url=ws_url)
        self.video_stream: VideoStream = UnitreeCameraVideoStream(
            self.ws_client.send_message, fps=fps
        )
        self._thread: Optional[threading.Thread] = None

    def register_message_callback(self, message_callback: Optional[Callable]):
        """
        Register a callback for processing VLM results.

        Parameters
        ----------
        callback : callable
            The callback function to process VLM results.
        """
        self.ws_client.register_message_callback(message_callback)

    def start(self):
        """
        Start the VLM provider.

        Initializes and starts the websocket client, video stream, and processing thread
        if not already running.
        """
        if self._thread and self._thread.is_alive():
            return

        self.running = True
        self.ws_client.start()
        self.video_stream.start()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        """
        Main loop for the VLM provider.

        Continuously processes video frames and sends them to the VLM service
        for analysis.
        """
        while self.running:
            try:
                time.sleep(0.1)
            except Exception as e:
                logging.error(f"Error in VLM provider: {e}")

    def stop(self):
        """
        Stop the VLM provider.

        Stops the websocket client, video stream, and processing thread.
        """
        self.running = False
        if self._thread:
            self.video_stream.stop()
            self.ws_client.stop()
            self._thread.join()
