import logging
import threading
import time
from typing import Optional

import numpy as np
import pyrealsense2 as rs

from providers.singleton import singleton


@singleton
class IntelDepthCameraObstacleProvider:
    """Provider for depth camera collision avoidance using Intel RealSense.

    This provider reads depth data from a downward-facing camera and detects
    obstacles beneath the robot for collision avoidance.
    """

    def __init__(
        self,
        depth_threshold: float = 0.3,  # Minimum safe distance in meters
        fps: int = 30,  # D435i supports 30fps at max resolution
        width: int = 1280,  # D435i max resolution
        height: int = 720,
    ):
        """Initialize the depth camera provider.

        Args:
            depth_threshold: Minimum safe distance to ground/obstacles in meters
            fps: Frames per second for the depth camera
            width: Width of the depth image
            height: Height of the depth image
        """
        self.depth_threshold = depth_threshold
        self.fps = fps
        self.width = width
        self.height = height

        # RealSense pipeline
        self.pipeline = None
        self.config = None
        self.depth_scale = 0.001  # Default value, will be updated from sensor

        # Thread management
        self._thread = None
        self._running = False
        self._lock = threading.Lock()

        # Obstacle detection results
        self._obstacle_detected = False
        self._min_distance = None
        self._depth_frame = None

    def start(self):
        """Start the depth camera provider."""
        if self._running:
            logging.warning("Depth camera provider already running")
            return

        # Configure RealSense pipeline
        self.pipeline = rs.pipeline()
        self.config = rs.config()

        # Enable depth stream
        self.config.enable_stream(
            rs.stream.depth, self.width, self.height, rs.format.z16, self.fps
        )

        # Start pipeline
        profile = self.pipeline.start(self.config)

        # Get depth sensor
        depth_sensor = profile.get_device().first_depth_sensor()
        self.depth_scale = depth_sensor.get_depth_scale()
        logging.info(f"Depth scale: {self.depth_scale}")

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

        logging.info("Depth camera provider started successfully")

    def stop(self):
        """Stop the depth camera provider."""
        logging.info("Stopping depth camera provider")
        self._running = False

        if self._thread:
            self._thread.join(timeout=5.0)

        if self.pipeline:
            self.pipeline.stop()

        logging.info("Depth camera provider stopped")

    def _run(self):
        """Main processing loop running in separate thread."""
        while self._running:
            try:
                # Wait for frames
                frames = self.pipeline.wait_for_frames(timeout_ms=1000)

                # Get depth frame
                depth_frame = frames.get_depth_frame()
                if not depth_frame:
                    continue

                # Convert to numpy array
                depth_image = np.asanyarray(depth_frame.get_data())

                # Process depth data
                self._process_depth_frame(depth_image)

                # Store frame for external access
                with self._lock:
                    self._depth_frame = depth_image

            except Exception as e:
                logging.error(f"Error in depth processing loop: {e}")
                time.sleep(0.1)

    def _process_depth_frame(self, depth_image: np.ndarray):
        """Process depth frame to detect obstacles.

        Args:
            depth_image: Depth image as numpy array (values in mm)
        """
        # Convert depth values from mm to meters
        depth_m = depth_image * self.depth_scale

        # Filter valid depth values (ignore 0 values which mean no reading)
        valid_depths = depth_m[depth_m > 0]

        if len(valid_depths) > 0:
            # Get minimum distance
            min_distance = np.min(valid_depths)

            # Update detection status
            with self._lock:
                self._obstacle_detected = min_distance < self.depth_threshold
                self._min_distance = min_distance
        else:
            with self._lock:
                self._obstacle_detected = False
                self._min_distance = None

    @property
    def obstacle_detected(self) -> bool:
        """Check if any obstacle is detected below the threshold."""
        with self._lock:
            return self._obstacle_detected

    @property
    def min_distance(self) -> Optional[float]:
        """Get minimum distance to obstacle in meters."""
        with self._lock:
            return self._min_distance

    @property
    def is_running(self) -> bool:
        """Check if the provider is running."""
        return self._running

    @property
    def depth_frame(self) -> Optional[np.ndarray]:
        """Get the latest depth frame."""
        with self._lock:
            return self._depth_frame.copy() if self._depth_frame is not None else None
