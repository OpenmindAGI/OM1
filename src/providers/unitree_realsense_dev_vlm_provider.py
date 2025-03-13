import base64
import glob
import logging
import os
import threading
import time
from typing import Callable, Optional

import cv2
from om1_utils import ws
from om1_vlm import VideoStream

from .singleton import singleton

root_package_name = __name__.split(".")[0] if "." in __name__ else __name__
logger = logging.getLogger(root_package_name)

# Resize target for video stream
TARGET_WIDTH = 640
TARGET_HEIGHT = 480


class UnitreeRealSenseDevVideoStream(VideoStream):
    """
    Manages video capture and streaming from a camera device.

    Captures frames from a camera, encodes them to base64, and sends them
    through the callback. Supports both macOS and Linux devices.

    Parameters
    ----------
    frame_callback : Optional[Callable[[str], None]]
        Callback function to handle processed frame data.
    fps : Optional[int]
        Frames per second to capture (default: 30).
    """

    def on_video(self):
        """
        Main video capture and processing loop.

        Continuously captures frames from the camera, encodes them to base64,
        and sends them through the callback. If too many consecutive frame read
        errors occur, it will attempt to switch to another camera device.

        This method catches all exceptions so that failures do not affect other
        threads or processes.
        """
        tried_devices = set()
        try:
            # Find and open the initial camera device.
            current_cam = self._find_rgb_device(skip_devices=tried_devices)
            if current_cam is None:
                logger.error("No viable RGB camera found.")
                return
            tried_devices.add(current_cam)

            self._cap = self._open_camera(current_cam)
            while self._cap is None:
                # If opening the current camera failed, try the next one.
                current_cam = self._find_rgb_device(skip_devices=tried_devices)
                if current_cam is None:
                    logger.error("No viable camera devices found.")
                    return
                tried_devices.add(current_cam)
                self._cap = self._open_camera(current_cam)

            failure_count = 0
            max_retries = 30  # Maximum allowed consecutive read failures. This is after approximately 3 seconds.

            while self.running:
                ret, frame = self._cap.read()
                if not ret:
                    failure_count += 1
                    logger.error(
                        "Error reading frame from video stream (failure %d/%d)",
                        failure_count,
                        max_retries,
                    )
                    time.sleep(0.1)

                    if failure_count >= max_retries:
                        logger.error(
                            "Too many frame read errors. Trying another camera device."
                        )
                        self._cap.release()
                        new_cam = self._find_rgb_device(skip_devices=tried_devices)
                        if new_cam is None:
                            logger.error(
                                "No viable camera devices found. Exiting video capture loop."
                            )
                            break
                        tried_devices.add(new_cam)
                        self._cap = self._open_camera(new_cam)

                        # If the new device also fails to open, continue trying.
                        while self._cap is None:
                            new_cam = self._find_rgb_device(skip_devices=tried_devices)
                            if new_cam is None:
                                logger.error(
                                    "No viable camera devices found. Exiting video capture loop."
                                )
                                break
                            tried_devices.add(new_cam)
                            self._cap = self._open_camera(new_cam)
                        failure_count = (
                            0  # Reset failure counter after switching devices
                        )
                    continue  # Skip processing for this iteration

                failure_count = 0  # Reset on a successful read

                # Convert frame to base64, and catch any encoding errors.
                try:
                    _, buffer = cv2.imencode(
                        ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80]
                    )
                    frame_data = base64.b64encode(buffer).decode("utf-8")
                except Exception as e:
                    logger.exception("Error encoding frame: %s", e)
                    continue

                # Invoke the callback; catch exceptions so one bad callback won't crash the thread.
                try:
                    if self.frame_callback:
                        self.frame_callback(frame_data)
                except Exception as e:
                    logger.exception("Error in frame callback: %s", e)

                time.sleep(self.frame_delay)
        except Exception as e:
            logger.exception("Unhandled error in video stream: %s", e)
        finally:
            if self._cap:
                self._cap.release()
                logger.info("Released video capture device")

    def _open_camera(self, cam):
        """
        Attempt to open the camera device and set desired properties.

        Parameters
        ----------
        cam : str
            The device path (e.g., '/dev/video0')

        Returns
        -------
        cv2.VideoCapture or None
            The opened capture device, or None if it could not be opened.
        """
        cap = cv2.VideoCapture(cam)
        if not cap.isOpened():
            logger.error("Error opening video stream from %s", cam)
            return None
        try:
            cap.set(cv2.CAP_PROP_FPS, self.fps)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, TARGET_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, TARGET_HEIGHT)
        except Exception as e:
            logger.exception(
                "Error setting camera properties for device %s: %s", cam, e
            )
        return cap

    def _find_rgb_device(self, skip_devices=None):
        """
        Find the first viable RGB camera device supporting common RGB formats.
        Optionally skips devices listed in skip_devices.

        Parameters
        ----------
        skip_devices : set, optional
            A set of device paths to ignore.

        Returns
        -------
        str or None
            The first viable RGB device, or None if none is found.
        """
        if skip_devices is None:
            skip_devices = set()

        try:
            video_devices = sorted(glob.glob("/dev/video*"))
        except Exception as e:
            logger.exception("Failed to list video devices: %s", e)
            return None

        for device in video_devices:
            if device in skip_devices:
                continue
            try:
                cmd = f"v4l2-ctl --device={device} --list-formats"
                formats = os.popen(cmd).read()
            except Exception as e:
                logger.exception("Failed to run command '%s': %s", cmd, e)
                continue

            try:
                if "MJPG" in formats or "YUYV" in formats:
                    logger.info(
                        "Found RGB device at %s with formats: %s", device, formats
                    )
                    return device
            except Exception as e:
                logger.exception(
                    "Error processing formats for device %s: %s", device, e
                )

        logger.warning("No RGB device found")
        return None


@singleton
class UnitreeRealSenseDevVLMProvider:
    """
    VLM Provider that handles audio streaming and websocket communication.

     This class implements a singleton pattern to manage audio input streaming and websocket
     communication for vlm services. It runs in a separate thread to handle
     continuous vlm processing.

     Parameters
     ----------
     ws_url : str
         The websocket URL for the ASR service connection.
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
        self.video_stream: VideoStream = UnitreeRealSenseDevVideoStream(
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
            self._thread.join(timeout=5)
