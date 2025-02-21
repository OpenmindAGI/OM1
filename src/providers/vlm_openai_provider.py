import logging
import threading
import time
from typing import Callable, Optional

from om1_vlm import VideoStream
from openai import AsyncOpenAI

from .singleton import singleton


@singleton
class VLMOpenAIProvider:
    """
    VLM Provider that handles video streaming and OpenAI API communication.

     This class implementationements a singleton pattern to manage video input streaming and API
     communication for vlm services. It runs in a separate thread to handle
     continuous vlm processing.

     Parameters
     ----------
     llm_config : LLMConfig
         Configuration for the LLM service.
     fps : int
         Frames per second for the video stream.
    """

    def __init__(self, base_url: str, api_key: str, fps: int = 10):
        """
        Initialize the VLM Provider.

        Parameters
        ----------
        llm_config : LLMConfig
            Configuration for the LLM service.
        """
        self.running: bool = False
        self.api_client: AsyncOpenAI = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.video_stream: VideoStream = VideoStream(
            frame_callback=self._process_frame, fps=fps
        )
        self._thread: Optional[threading.Thread] = None
        self.message_callback: Optional[Callable] = None
        logging.info("VLM OpenAI Provider initialized")

    async def _process_frame(self, frame: str):
        """
        Process a video frame using the LLM API.

        Parameters
        ----------
        frame : str
            The base64 encoded video frame to process.
        """
        processing_start = time.perf_counter()
        try:
            response = await self.api_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "What's in this image?"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{frame}",
                                    "detail": "low",
                                },
                            },
                        ],
                    }
                ],
                max_tokens=300,
            )
            processing_latency = time.perf_counter() - processing_start
            logging.debug(f"Processing latency: {processing_latency:.3f} seconds")
            logging.debug(f"OpenAI LLM VLM Response: {response}")
            if self.message_callback:
                self.message_callback(response)
        except Exception as e:
            logging.error(f"Error processing frame: {e}")

    def register_message_callback(self, message_callback: Optional[Callable]):
        """
        Register a callback for processing VLM results.

        Parameters
        ----------
        callback : callable
            The callback function to process VLM results.
        """
        self.message_callback = message_callback

    def start(self):
        """
        Start the VLM provider.

        Initializes and starts the video stream and processing thread
        if not already running.
        """
        if self._thread and self._thread.is_alive():
            return

        self.running = True
        self.video_stream.start()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logging.info("VLM LLM Provider started")

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

        Stops the video stream and processing thread.
        """
        self.running = False
        if self._thread:
            self.video_stream.stop()
            self._thread.join(timeout=5)
