import asyncio
import logging
import random
import time
import json
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple

import cv2
import numpy as np
import mediapipe as mp  # We need to add this to dependencies

from inputs.base import SensorConfig
from inputs.base.loop import FuserInput
from providers.io_provider import IOProvider


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
    gesture : str
        Detected gesture
    """
    
    timestamp: float
    message: str
    gesture: str = ""


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


class GestureRecognition(FuserInput[cv2.typing.MatLike]):
    """
    Real-time gesture recognition using webcam input.
    
    Uses MediaPipe for hand detection and gesture classification.
    Processes video frames to detect hands and classify gestures.
    Interprets gestures and provides natural language descriptions.
    """
    
    def __init__(self, config: SensorConfig = SensorConfig()):
        """
        Initialize GestureRecognition instance.
        """
        super().__init__(config)
        
        # Track IO
        self.io_provider = IOProvider()
        
        # Initialize MediaPipe Hands
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        self.hands = self.mp_hands.Hands(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            max_num_hands=2
        )
        
        self.have_cam = check_webcam()
        
        # Start capturing video, if we have a webcam
        self.cap = None
        if self.have_cam:
            self.cap = cv2.VideoCapture(0)
        
        # Initialize gesture label
        self.detected_gesture = ""
        
        # Define gesture meanings
        self.gesture_meanings = {
            "thumbs_up": "approval or agreement",
            "thumbs_down": "disapproval or disagreement",
            "open_palm": "stop or greeting",
            "pointing": "indicating direction or object of interest",
            "fist": "determination or readiness",
            "peace": "peace or victory sign",
            "wave": "greeting or goodbye",
            "ok_sign": "confirmation or approval",
            "pinch": "precision or picking something small"
        }
        
        # Messages buffer
        self.messages: list[Message] = []
    
    async def _poll(self) -> Optional[cv2.typing.MatLike]:
        """
        Capture frame from webcam.
        
        Returns
        -------
        cv2.typing.MatLike
            Captured video frame
        """
        await asyncio.sleep(0.5)
        
        # Capture a frame every 500 ms
        if self.have_cam:
            ret, frame = self.cap.read()
            return frame
    
    def _detect_gesture(self, hand_landmarks) -> str:
        """
        Identify gestures based on hand landmark positions.
        
        Parameters
        ----------
        hand_landmarks : mediapipe.framework.formats.landmark_pb2.NormalizedLandmarkList
            MediaPipe hand landmarks
        
        Returns
        -------
        str
            Identified gesture
        """
        # Get landmark positions
        landmarks = []
        for lm in hand_landmarks.landmark:
            landmarks.append([lm.x, lm.y, lm.z])
        
        # Convert to numpy array for easier calculations
        landmarks = np.array(landmarks)
        
        # Basic gesture detection based on finger positions
        # Thumb
        thumb_tip = landmarks[4]
        thumb_ip = landmarks[3]
        
        # Index finger
        index_tip = landmarks[8]
        index_dip = landmarks[7]
        index_pip = landmarks[6]
        index_mcp = landmarks[5]
        
        # Middle finger
        middle_tip = landmarks[12]
        middle_dip = landmarks[11]
        middle_pip = landmarks[10]
        
        # Ring finger
        ring_tip = landmarks[16]
        ring_pip = landmarks[14]
        
        # Pinky
        pinky_tip = landmarks[20]
        pinky_pip = landmarks[18]
        
        # Wrist
        wrist = landmarks[0]
        
        # Check for thumbs up
        if (thumb_tip[1] < thumb_ip[1] and 
            index_tip[1] > index_mcp[1] and 
            middle_tip[1] > middle_pip[1] and
            ring_tip[1] > ring_pip[1] and
            pinky_tip[1] > pinky_pip[1]):
            return "thumbs_up"
        
        # Check for thumbs down
        if (thumb_tip[1] > thumb_ip[1] and 
            index_tip[1] < index_mcp[1] and 
            middle_tip[1] < middle_pip[1] and
            ring_tip[1] < ring_pip[1] and
            pinky_tip[1] < pinky_pip[1]):
            return "thumbs_down"
        
        # Check for open palm
        if (index_tip[1] < index_pip[1] and 
            middle_tip[1] < middle_pip[1] and
            ring_tip[1] < ring_pip[1] and
            pinky_tip[1] < pinky_pip[1]):
            return "open_palm"
        
        # Check for pointing (index finger extended)
        if (index_tip[1] < index_dip[1] and 
            middle_tip[1] > middle_pip[1] and
            ring_tip[1] > ring_pip[1] and
            pinky_tip[1] > pinky_pip[1]):
            return "pointing"
        
        # Check for fist
        if (index_tip[1] > index_pip[1] and 
            middle_tip[1] > middle_pip[1] and
            ring_tip[1] > ring_pip[1] and
            pinky_tip[1] > pinky_pip[1]):
            return "fist"
        
        # Check for peace sign
        if (index_tip[1] < index_pip[1] and 
            middle_tip[1] < middle_pip[1] and
            ring_tip[1] > ring_pip[1] and
            pinky_tip[1] > pinky_pip[1]):
            return "peace"
        
        # If no specific gesture detected
        return "unknown"
    
    async def _raw_to_text(self, raw_input: cv2.typing.MatLike) -> Message:
        """
        Process video frame for gesture detection.
        
        Parameters
        ----------
        raw_input : cv2.typing.MatLike
            Input video frame
        
        Returns
        -------
        Message
            Timestamped gesture detection result
        """
        if not self.have_cam:
            # Simulate a model response
            gestures = list(self.gesture_meanings.keys())
            random_gesture = random.choice(gestures)
            meaning = self.gesture_meanings.get(random_gesture, "unknown gesture")
            message = f"I see a person making a {random_gesture} gesture, which typically means {meaning}."
            return Message(timestamp=time.time(), message=message, gesture=random_gesture)
        
        frame = raw_input
        
        # Convert the BGR image to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Process the frame and detect hands
        results = self.hands.process(rgb_frame)
        
        # Reset gesture detection
        self.detected_gesture = "no_gesture"
        
        # Check if hands are detected
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                # Draw landmarks on frame (for debugging)
                self.mp_drawing.draw_landmarks(
                    frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
                
                # Detect gesture
                self.detected_gesture = self._detect_gesture(hand_landmarks)
        
        # Generate message based on detected gesture
        if self.detected_gesture == "no_gesture":
            message = "I don't see any hand gestures at the moment."
        else:
            meaning = self.gesture_meanings.get(self.detected_gesture, "unknown gesture")
            message = f"I see a person making a {self.detected_gesture} gesture, which typically means {meaning}."
        
        logging.info(f"GestureRecognition: {message}")
        
        return Message(timestamp=time.time(), message=message, gesture=self.detected_gesture)
    
    async def raw_to_text(self, raw_input: cv2.typing.MatLike):
        """
        Convert raw input to processed text and manage buffer.
        
        Parameters
        ----------
        raw_input : cv2.typing.MatLike
            Raw input to be processed
        """
        pending_message = await self._raw_to_text(raw_input)
        
        if pending_message is not None:
            self.messages.append(pending_message)
    
    def formatted_latest_buffer(self) -> Optional[str]:
        """
        Format and clear the latest buffer contents.
        
        Returns
        -------
        Optional[str]
            Formatted string of buffer contents or None if buffer is empty
        """
        if len(self.messages) == 0:
            return None
        
        latest_message = self.messages[-1]
        
        result = f"""
{self.__class__.__name__} INPUT
// START
{latest_message.message}
// END
"""
        
        self.io_provider.add_input(
            self.__class__.__name__, latest_message.message, latest_message.timestamp)
        self.messages = []
        
        return result
