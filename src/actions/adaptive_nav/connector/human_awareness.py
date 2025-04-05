import logging
import math
import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Tuple
import zenoh

from zenoh_idl import sensor_msgs


@dataclass
class HumanDetection:
    """Information about a detected human"""
    id: int
    position_x: float
    position_y: float
    velocity_x: float
    velocity_y: float
    confidence: float
    last_seen: float  # timestamp


class PersonalSpaceModel:
    """
    Model of human personal space for social navigation.
    
    Implements a proxemic model of human personal space based on
    Hall's proxemic theory, allowing robots to maintain appropriate
    distances during navigation.
    """
    def __init__(self):
        # Distances in meters based on proxemic theory
        self.intimate_distance = 0.45
        self.personal_distance = 1.2
        self.social_distance = 3.6
        
        # Parameters for the elliptical personal space model
        self.front_scaling = 1.5  # Personal space extends more in front
        self.side_scaling = 1.0
        self.back_scaling = 0.8  # Less personal space needed behind
        
        # Additional cost scaling factors
        self.personal_space_cost = 2.0  # Cost multiplier for personal space
        self.social_space_cost = 0.5  # Cost multiplier for social space
    
    def get_personal_space_cost(self, 
                               robot_x: float, robot_y: float, 
                               human_x: float, human_y: float, 
                               human_orientation: float) -> float:
        """
        Calculate the cost of a position relative to human personal space.
        
        Parameters
        ----------
        robot_x, robot_y : float
            Robot's position
        human_x, human_y : float
            Human's position
        human_orientation : float
            Human's orientation in radians
            
        Returns
        -------
        float
            Cost value (higher = more intrusive)
        """
        # Calculate distance from robot to human
        dx = robot_x - human_x
        dy = robot_y - human_y
        distance = math.sqrt(dx*dx + dy*dy)
        
        # Calculate angle of robot relative to human orientation
        angle_to_robot = math.atan2(dy, dx) - human_orientation
        # Normalize to [-pi, pi]
        while angle_to_robot > math.pi:
            angle_to_robot -= 2 * math.pi
        while angle_to_robot < -math.pi:
            angle_to_robot += 2 * math.pi
        
        # Determine scaling factor based on relative position
        if abs(angle_to_robot) < math.pi/4:  # Front
            scaling = self.front_scaling
        elif abs(angle_to_robot) > 3*math.pi/4:  # Back
            scaling = self.back_scaling
        else:  # Sides
            scaling = self.side_scaling
        
        # Calculate personal space boundary at this angle
        personal_boundary = self.personal_distance * scaling
        social_boundary = self.social_distance * scaling
        
        # Calculate cost based on distance
        cost = 0.0
        if distance < self.intimate_distance:
            # Very high cost in intimate space
            cost = 10.0
        elif distance < personal_boundary:
            # Cost in personal space decreases with distance
            normalized_dist = (distance - self.intimate_distance) / (personal_boundary - self.intimate_distance)
            cost = self.personal_space_cost * (1.0 - normalized_dist)
        elif distance < social_boundary:
            # Lower cost in social space
            normalized_dist = (distance - personal_boundary) / (social_boundary - personal_boundary)
            cost = self.social_space_cost * (1.0 - normalized_dist)
        
        return cost


class HumanAwarenessModule:
    """
    Module for human detection and social awareness in navigation.
    
    This module tracks humans in the environment and provides
    social navigation costs to help the robot maintain appropriate
    distances and behaviors around humans.
    """
    def __init__(self):
        # Zenoh connection
        self.zenoh_conf = zenoh.Config()
        self.zenoh_session = None
        self.person_subscriber = None
        
        # Human tracking
        self.humans: List[HumanDetection] = []
        self.human_tracking_timeout = 5.0  # seconds
        
        # Personal space model
        self.personal_space = PersonalSpaceModel()
        
        # VLM-based human detection (can be enabled if available)
        self.use_vlm = False
        self.vlm_subscriber = None
    
    async def initialize(self):
        """Initialize the human awareness module"""
        try:
            self.zenoh_session = zenoh.open(self.zenoh_conf)
            
            # Subscribe to person detection topic
            # Adjust topic name based on what's available in your system
            self.person_subscriber = self.zenoh_session.declare_subscriber(
                "*/person_detections", self._person_callback
            )
            
            # Optionally subscribe to VLM-based detection if available
            if self.use_vlm:
                self.vlm_subscriber = self.zenoh_session.declare_subscriber(
                    "*/vlm_detections", self._vlm_callback
                )
            
            logging.info("Human awareness module initialized")
            return True
        except Exception as e:
            logging.error(f"Failed to initialize human awareness module: {e}")
            return False
    
    def _person_callback(self, sample):
        """Process person detection data"""
        try:
            # This assumes a custom person detection message format
            # Adapt as needed based on your actual message format
            detections = sensor_msgs.PersonDetections.deserialize(sample.payload.to_bytes())
            
            current_time = detections.header.stamp.sec + detections.header.stamp.nanosec * 1e-9
            
            # Update human detections
            for person in detections.detections:
                # Extract person position and velocity if available
                human_id = person.id
                position_x = person.pose.position.x
                position_y = person.pose.position.y
                
                # Extract velocity if available, otherwise use 0
                velocity_x = getattr(person, "velocity_x", 0.0)
                velocity_y = getattr(person, "velocity_y", 0.0)
                
                # Extract confidence if available
                confidence = getattr(person, "confidence", 0.8)
                
                # Check if this human is already being tracked
                existing_idx = next((i for i, h in enumerate(self.humans) 
                                    if h.id == human_id), None)
                
                if existing_idx is not None:
                    # Update existing human
                    self.humans[existing_idx] = HumanDetection(
                        id=human_id,
                        position_x=position_x,
                        position_y=position_y,
                        velocity_x=velocity_x,
                        velocity_y=velocity_y,
                        confidence=confidence,
                        last_seen=current_time
                    )
                else:
                    # Add new human
                    self.humans.append(HumanDetection(
                        id=human_id,
                        position_x=position_x,
                        position_y=position_y,
                        velocity_x=velocity_x,
                        velocity_y=velocity_y,
                        confidence=confidence,
                        last_seen=current_time
                    ))
            
            # Clean up old detections
            self._cleanup_old_detections(current_time)
            
        except Exception as e:
            logging.error(f"Error processing person detection: {e}")
    
    def _vlm_callback(self, sample):
        """Process VLM-based human detection"""
        try:
            # Parse VLM detection results
            # This is a simplified example - adapt based on your VLM output format
            vlm_result = sample.payload.decode('utf-8')
            
            # For simplicity, we're assuming a JSON format string
            # with detected objects and their bounding boxes
            import json
            detections = json.loads(vlm_result)
            
            current_time = time.time()
            human_count = 0
            
            # Process human detections from VLM
            for obj in detections.get("objects", []):
                if obj.get("class") in ["person", "human"]:
                    human_count += 1
                    
                    # For demo purposes, we're creating basic detections
                    # In a real implementation, you'd convert bounding boxes to world coordinates
                    self.humans.append(HumanDetection(
                        id=1000 + human_count,  # Use ID offset to avoid conflicts
                        position_x=1.0,  # Placeholder values
                        position_y=0.0,
                        velocity_x=0.0,
                        velocity_y=0.0,
                        confidence=obj.get("confidence", 0.7),
                        last_seen=current_time
                    ))
            
            # Clean up old detections
            self._cleanup_old_detections(current_time)
            
        except Exception as e:
            logging.error(f"Error processing VLM detection: {e}")
    
    def _cleanup_old_detections(self, current_time):
        """Remove old human detections that haven't been seen recently"""
        self.humans = [human for human in self.humans 
                      if (current_time - human.last_seen) <= self.human_tracking_timeout]
    
    def get_social_navigation_cost(self, x: float, y: float) -> float:
        """
        Calculate the social navigation cost for a given position.
        
        This function evaluates how socially appropriate a position is
        based on the location of humans and their personal space.
        
        Parameters
        ----------
        x, y : float
            Position to evaluate
            
        Returns
        -------
        float
            Social cost (higher = less socially appropriate)
        """
        if not self.humans:
            return 0.0
        
        total_cost = 0.0
        
        for human in self.humans:
            # Calculate human's predicted orientation based on velocity
            if abs(human.velocity_x) > 0.1 or abs(human.velocity_y) > 0.1:
                # Use velocity to estimate orientation
                human_orientation = math.atan2(human.velocity_y, human.velocity_x)
            else:
                # If human isn't moving, assume they're facing the robot
                dx = x - human.position_x
                dy = y - human.position_y
                human_orientation = math.atan2(dy, dx) + math.pi  # Add pi to face robot
            
            # Get personal space cost for this human
            cost = self.personal_space.get_personal_space_cost(
                x, y, human.position_x, human.position_y, human_orientation
            )
            
            # Scale by confidence
            cost *= human.confidence
            
            total_cost += cost
        
        return total_cost
    
    def get_preferred_approach_direction(self, 
                                        target_x: float, target_y: float, 
                                        human_x: float, human_y: float) -> float:
        """
        Calculate the preferred approach direction for social interaction.
        
        When approaching a human for interaction, this calculates the
        best direction to approach from.
        
        Parameters
        ----------
        target_x, target_y : float
            Target position to approach
        human_x, human_y : float
            Human's position
            
        Returns
        -------
        float
            Preferred approach angle in radians
        """
        # Humans typically prefer approaches from the front
        # Calculate vector from human to target
        dx = target_x - human_x
        dy = target_y - human_y
        
        # Standard approach is from the front at a comfortable distance
        base_approach = math.atan2(dy, dx)
        
        # Find nearby humans that might block this approach
        blocked = False
        for other_human in self.humans:
            if other_human.position_x == human_x and other_human.position_y == human_y:
                continue  # Skip the target human
                
            # Check if other human is between target and approach path
            # Simplified check - could be more sophisticated
            other_dx = other_human.position_x - human_x
            other_dy = other_human.position_y - human_y
            other_dist = math.sqrt(other_dx*other_dx + other_dy*other_dy)
            other_angle = math.atan2(other_dy, other_dx)
            
            angle_diff = abs(other_angle - base_approach)
            while angle_diff > math.pi:
                angle_diff = abs(angle_diff - 2*math.pi)
                
            if angle_diff < 0.5 and other_dist < 2.0:  # If within 30 degrees and 2m
                blocked = True
                break
        
        if blocked:
            # Try approaching from the side instead
            return base_approach + math.pi/2
        
        return base_approach
    
    def get_humans_in_path(self, path_points: List[Tuple[float, float]], 
                          threshold_distance: float = 1.0) -> List[HumanDetection]:
        """
        Find humans that are near the planned path.
        
        Parameters
        ----------
        path_points : List[Tuple[float, float]]
            List of (x, y) coordinates along the path
        threshold_distance : float
            Maximum distance to consider a human "in the path"
            
        Returns
        -------
        List[HumanDetection]
            List of humans near the path
        """
        if not path_points or not self.humans:
            return []
            
        humans_in_path = []
        
        for human in self.humans:
            # Check distance from human to each path segment
            min_distance = float('inf')
            
            for i in range(len(path_points) - 1):
                p1 = path_points[i]
                p2 = path_points[i + 1]
                
                # Calculate distance from human to line segment
                distance = self._point_to_segment_distance(
                    human.position_x, human.position_y, 
                    p1[0], p1[1], p2[0], p2[1]
                )
                
                min_distance = min(min_distance, distance)
                
            if min_distance <= threshold_distance:
                humans_in_path.append(human)
                
        return humans_in_path
    
    def _point_to_segment_distance(self, px, py, x1, y1, x2, y2):
        """Calculate distance from point (px,py) to line segment (x1,y1)-(x2,y2)"""
        # Calculate squared length of segment
        l2 = (x2 - x1)**2 + (y2 - y1)**2
        
        if l2 == 0:  # If segment is a point
            return math.sqrt((px - x1)**2 + (py - y1)**2)
            
        # Calculate projection ratio
        t = max(0, min(1, ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / l2))
        
        # Calculate projection point
        projection_x = x1 + t * (x2 - x1)
        projection_y = y1 + t * (y2 - y1)
        
        # Return distance to projection
        return math.sqrt((px - projection_x)**2 + (py - projection_y)**2)
    
    def cleanup(self):
        """Clean up resources"""
        if self.zenoh_session:
            if self.person_subscriber:
                self.person_subscriber.undeclare()
            if self.vlm_subscriber:
                self.vlm_subscriber.undeclare()
            self.zenoh_session.close() 