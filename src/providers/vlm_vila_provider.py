import logging
import threading
import time
from typing import Callable, Optional

from om1_utils import ws
from om1_vlm import VideoStream

from .singleton import singleton


@singleton
class VLMVilaProvider:
    """
    VLM Provider that handles audio streaming and websocket communication.

    This class implements a singleton pattern to manage audio input streaming and websocket
    communication for vlm services. It runs in a separate thread to handle
    continuous vlm processing.
    """

    def __init__(self, ws_url: str, fps: int = 30, stream_url: Optional[str] = None):
        """
        Initialize the VLM Provider.

        Parameters
        ----------
        ws_url : str
            The websocket URL for the VLM service connection.
        fps : int
            The fps for the VLM service connection.
        stream_url : str, optional
            The URL for the video stream. If not provided, defaults to None.
        """
        self.running: bool = False
        self.ws_client: ws.Client = ws.Client(url=ws_url)
        self.stream_ws_client: Optional[ws.Client] = (
            ws.Client(url=stream_url) if stream_url else None
        )
        self.video_stream: VideoStream = VideoStream(
            self.ws_client.send_message, fps=fps
        )
        self._thread: Optional[threading.Thread] = None

    def register_frame_callback(self, video_callback: Optional[Callable]):
        """
        Register a callback for processing video frames.

        Parameters
        ----------
        video_callback : callable
            The callback function to process video frames.
        """
        self.video_stream.register_frame_callback(video_callback)

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

        if self.stream_ws_client:
            self.stream_ws_client.start()
            self.video_stream.register_frame_callback(
                self.stream_ws_client.send_message
            )

        logging.info("Vila VLM provider started")

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
                logging.error(f"Error in Vila VLM provider: {e}")

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

        if self.stream_ws_client:
            self.stream_ws_client.stop()
