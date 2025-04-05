import asyncio
import logging
import math
import json
import time
from typing import List, Dict, Any, Optional, Tuple
import zenoh

from actions.adaptive_nav.interface import Point2D, NavigationMode


class NavigationVisualizer:
    """
    Visualization tool for debugging and monitoring adaptive navigation.
    
    This module provides real-time visualization of the robot's path planning,
    obstacle detection, and navigation progress through a web interface.
    """
    def __init__(self):
        # Zenoh connection
        self.zenoh_conf = zenoh.Config()
        self.zenoh_session = None
        self.vis_publisher = None
        
        # Visualization state
        self.current_position = (0.0, 0.0)
        self.current_orientation = 0.0
        self.planned_path = []
        self.obstacles = []
        self.target_position = None
        self.navigation_mode = NavigationMode.NORMAL
        self.humans = []
        
        # Frame ID counter for visualization
        self.frame_id = 0
        
        # Update rate and the last update time
        self.update_rate = 5.0  # Hz
        self.last_update = 0.0
    
    async def initialize(self):
        """Initialize the visualization module"""
        try:
            self.zenoh_session = zenoh.open(self.zenoh_conf)
            
            # Create publisher for visualization data
            self.vis_publisher = self.zenoh_session.declare_publisher(
                "nav_visualization"
            )
            
            logging.info("Navigation visualizer initialized")
            return True
        except Exception as e:
            logging.error(f"Failed to initialize navigation visualizer: {e}")
            return False
    
    def update_robot_state(self, position: Tuple[float, float], orientation: float):
        """Update the robot's current position and orientation"""
        self.current_position = position
        self.current_orientation = orientation
    
    def update_planned_path(self, path: List[Point2D]):
        """Update the planned path"""
        self.planned_path = [(p.x, p.y) for p in path]
    
    def update_obstacles(self, obstacles: List[Tuple[float, float, float]]):
        """
        Update the obstacle list.
        
        Parameters
        ----------
        obstacles : List[Tuple[float, float, float]]
            List of obstacles as (x, y, radius)
        """
        self.obstacles = obstacles
    
    def update_target(self, target: Optional[Point2D]):
        """Update the navigation target"""
        self.target_position = (target.x, target.y) if target else None
    
    def update_navigation_mode(self, mode: NavigationMode):
        """Update the current navigation mode"""
        self.navigation_mode = mode
    
    def update_humans(self, humans: List[Dict[str, Any]]):
        """
        Update human detection data.
        
        Parameters
        ----------
        humans : List[Dict[str, Any]]
            List of human detections with position, velocity, etc.
        """
        self.humans = humans
    
    def publish_visualization(self, force: bool = False):
        """
        Publish visualization data to Zenoh.
        
        Parameters
        ----------
        force : bool
            Force publication even if not enough time has passed
        """
        current_time = time.time()
        
        # Only update at the configured rate unless forced
        if not force and (current_time - self.last_update) < (1.0 / self.update_rate):
            return
            
        self.last_update = current_time
        
        if not self.vis_publisher:
            return
            
        try:
            # Create visualization message
            vis_data = {
                "frame_id": self.frame_id,
                "timestamp": current_time,
                "robot": {
                    "position": self.current_position,
                    "orientation": self.current_orientation
                },
                "path": self.planned_path,
                "obstacles": self.obstacles,
                "target": self.target_position,
                "mode": self.navigation_mode,
                "humans": self.humans
            }
            
            # Increment frame ID
            self.frame_id += 1
            
            # Convert to JSON and publish
            json_data = json.dumps(vis_data)
            self.vis_publisher.put(json_data)
            
        except Exception as e:
            logging.error(f"Error publishing visualization data: {e}")
    
    def cleanup(self):
        """Clean up resources"""
        if self.zenoh_session:
            if self.vis_publisher:
                self.vis_publisher.undeclare()
            self.zenoh_session.close()
            self.zenoh_session = None


class NavigationLogger:
    """
    Logger for navigation events and performance metrics.
    
    Records various navigation events and metrics for later analysis
    and performance tuning.
    """
    def __init__(self, log_file: str = "navigation_log.jsonl"):
        self.log_file = log_file
        self.start_time = time.time()
        self.log_entries = []
        
        # Navigation stats
        self.total_distance = 0.0
        self.total_navigation_time = 0.0
        self.total_path_length = 0.0
        self.path_deviations = []
        self.obstacle_encounters = 0
        self.replanning_events = 0
        self.navigation_failures = 0
        self.navigation_successes = 0
        
        # Last recorded position for distance calculation
        self.last_position = None
    
    def log_start_navigation(self, target: Point2D, mode: NavigationMode):
        """Log start of a navigation task"""
        entry = {
            "type": "navigation_start",
            "timestamp": time.time() - self.start_time,
            "target": {"x": target.x, "y": target.y},
            "mode": mode
        }
        self.log_entries.append(entry)
        self.last_position = None
    
    def log_path_planning(self, path_length: float, path_points: List[Point2D], planning_time: float):
        """Log path planning results"""
        entry = {
            "type": "path_planning",
            "timestamp": time.time() - self.start_time,
            "path_length": path_length,
            "path_points": len(path_points),
            "planning_time": planning_time
        }
        self.log_entries.append(entry)
        self.total_path_length = path_length
    
    def log_position_update(self, position: Point2D):
        """Log robot position updates and calculate distance traveled"""
        if self.last_position:
            # Calculate distance moved
            dx = position.x - self.last_position[0]
            dy = position.y - self.last_position[1]
            distance = math.sqrt(dx*dx + dy*dy)
            self.total_distance += distance
            
            entry = {
                "type": "position_update",
                "timestamp": time.time() - self.start_time,
                "position": {"x": position.x, "y": position.y},
                "distance_moved": distance,
                "total_distance": self.total_distance
            }
            self.log_entries.append(entry)
        
        self.last_position = (position.x, position.y)
    
    def log_obstacle_detected(self, obstacle_position: Tuple[float, float], distance: float):
        """Log obstacle detection events"""
        entry = {
            "type": "obstacle_detected",
            "timestamp": time.time() - self.start_time,
            "position": {"x": obstacle_position[0], "y": obstacle_position[1]},
            "distance": distance
        }
        self.log_entries.append(entry)
        self.obstacle_encounters += 1
    
    def log_path_replanning(self, reason: str):
        """Log path replanning events"""
        entry = {
            "type": "path_replanning",
            "timestamp": time.time() - self.start_time,
            "reason": reason
        }
        self.log_entries.append(entry)
        self.replanning_events += 1
    
    def log_human_interaction(self, human_id: int, distance: float, interaction_type: str):
        """Log human interaction events"""
        entry = {
            "type": "human_interaction",
            "timestamp": time.time() - self.start_time,
            "human_id": human_id,
            "distance": distance,
            "interaction_type": interaction_type
        }
        self.log_entries.append(entry)
    
    def log_navigation_complete(self, success: bool, duration: float, message: str):
        """Log navigation completion"""
        entry = {
            "type": "navigation_complete",
            "timestamp": time.time() - self.start_time,
            "success": success,
            "duration": duration,
            "message": message,
            "total_distance": self.total_distance,
            "path_length": self.total_path_length,
            "obstacle_encounters": self.obstacle_encounters,
            "replanning_events": self.replanning_events
        }
        self.log_entries.append(entry)
        self.total_navigation_time += duration
        
        if success:
            self.navigation_successes += 1
        else:
            self.navigation_failures += 1
    
    def log_path_deviation(self, planned_point: Point2D, actual_point: Point2D):
        """Log deviation from planned path"""
        dx = planned_point.x - actual_point.x
        dy = planned_point.y - actual_point.y
        deviation = math.sqrt(dx*dx + dy*dy)
        
        entry = {
            "type": "path_deviation",
            "timestamp": time.time() - self.start_time,
            "deviation": deviation,
            "planned": {"x": planned_point.x, "y": planned_point.y},
            "actual": {"x": actual_point.x, "y": actual_point.y}
        }
        self.log_entries.append(entry)
        self.path_deviations.append(deviation)
    
    def get_navigation_stats(self) -> Dict[str, Any]:
        """Get summary statistics for navigation performance"""
        stats = {
            "total_distance": self.total_distance,
            "total_navigation_time": self.total_navigation_time,
            "navigation_successes": self.navigation_successes,
            "navigation_failures": self.navigation_failures,
            "success_rate": self.navigation_successes / (self.navigation_successes + self.navigation_failures) if (self.navigation_successes + self.navigation_failures) > 0 else 0,
            "average_replanning_per_navigation": self.replanning_events / (self.navigation_successes + self.navigation_failures) if (self.navigation_successes + self.navigation_failures) > 0 else 0,
            "average_path_deviation": sum(self.path_deviations) / len(self.path_deviations) if self.path_deviations else 0
        }
        return stats
    
    def save_log(self):
        """Save log to file"""
        try:
            with open(self.log_file, 'w') as f:
                for entry in self.log_entries:
                    f.write(json.dumps(entry) + '\n')
            logging.info(f"Navigation log saved to {self.log_file}")
        except Exception as e:
            logging.error(f"Error saving navigation log: {e}")
    
    def reset(self):
        """Reset the logger for a new navigation session"""
        self.log_entries = []
        self.total_distance = 0.0
        self.total_path_length = 0.0
        self.path_deviations = []
        self.obstacle_encounters = 0
        self.replanning_events = 0
        self.last_position = None 