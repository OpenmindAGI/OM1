import asyncio
import logging
import math
from typing import List, Optional
import zenoh

from actions.adaptive_nav.interface import NavigationMode, Point2D
from zenoh_idl import geometry_msgs


class MovementController:
    """
    Handles the execution of navigation paths by translating them into robot movement commands.
    
    This controller translates high-level navigation paths from the AdaptiveNavConnector
    into low-level velocity commands that the robot can execute.
    """
    def __init__(self):
        # Zenoh connection
        self.zenoh_conf = zenoh.Config()
        self.zenoh_session = None
        self.cmd_vel_publisher = None
        
        # Controller parameters
        self.lookahead_distance = 0.3  # meters
        self.k_linear = 0.5  # Linear velocity gain
        self.k_angular = 1.0  # Angular velocity gain
        self.max_linear_speed = 0.5  # m/s
        self.max_angular_speed = 1.0  # rad/s
        self.goal_tolerance = 0.1  # meters
        self.slow_down_distance = 0.5  # meters
        
        # State
        self.current_path = []
        self.current_path_index = 0
        self.is_executing = False
        self.is_paused = False
        
    async def initialize(self):
        """Initialize the movement controller"""
        try:
            self.zenoh_session = zenoh.open(self.zenoh_conf)
            self.cmd_vel_publisher = self.zenoh_session.declare_publisher("cmd_vel")
            logging.info("Movement controller initialized successfully")
            return True
        except Exception as e:
            logging.error(f"Failed to initialize movement controller: {e}")
            return False
    
    def set_navigation_mode(self, mode: NavigationMode):
        """Adjust controller parameters based on navigation mode"""
        if mode == NavigationMode.SAFE:
            self.max_linear_speed = 0.2
            self.max_angular_speed = 0.6
            self.lookahead_distance = 0.2
            self.slow_down_distance = 0.8
        elif mode == NavigationMode.NORMAL:
            self.max_linear_speed = 0.5
            self.max_angular_speed = 1.0
            self.lookahead_distance = 0.3
            self.slow_down_distance = 0.5
        elif mode == NavigationMode.EFFICIENT:
            self.max_linear_speed = 0.8
            self.max_angular_speed = 1.5
            self.lookahead_distance = 0.5
            self.slow_down_distance = 0.4
        elif mode == NavigationMode.SOCIAL:
            self.max_linear_speed = 0.4
            self.max_angular_speed = 0.8
            self.lookahead_distance = 0.4
            self.slow_down_distance = 0.6
        elif mode == NavigationMode.FOLLOW:
            self.max_linear_speed = 0.6
            self.max_angular_speed = 1.2
            self.lookahead_distance = 0.6
            self.slow_down_distance = 0.3
    
    def set_path(self, path: List[Point2D]):
        """Set a new path to follow"""
        self.current_path = path
        self.current_path_index = 0
        logging.info(f"New path set with {len(path)} points")
    
    def get_target_point(self, current_position: Point2D) -> Optional[Point2D]:
        """
        Get the target point along the path based on lookahead distance.
        
        This implements a pure pursuit algorithm to smoothly follow the path.
        """
        if not self.current_path or self.current_path_index >= len(self.current_path):
            return None
        
        # Start from the current index
        i = self.current_path_index
        
        # Find the first point that's at least lookahead_distance away
        while i < len(self.current_path):
            # Calculate distance to this point
            dx = self.current_path[i].x - current_position.x
            dy = self.current_path[i].y - current_position.y
            distance = math.sqrt(dx*dx + dy*dy)
            
            if distance >= self.lookahead_distance:
                return self.current_path[i]
            
            i += 1
            self.current_path_index = i
        
        # If we're here, we're close to the end of the path
        # Return the last point
        if len(self.current_path) > 0:
            return self.current_path[-1]
        
        return None
    
    def compute_velocity(self, current_position: Point2D, 
                         current_orientation: float, 
                         target_point: Point2D) -> tuple:
        """
        Compute linear and angular velocity to reach the target point.
        
        Uses a simple proportional controller for both linear and angular velocity.
        """
        # Calculate distance and angle to target
        dx = target_point.x - current_position.x
        dy = target_point.y - current_position.y
        distance = math.sqrt(dx*dx + dy*dy)
        
        # Calculate the angle to the target in the world frame
        target_angle = math.atan2(dy, dx)
        
        # Calculate the angle error (difference between current orientation and target angle)
        # Normalize to [-pi, pi]
        angle_error = target_angle - current_orientation
        while angle_error > math.pi:
            angle_error -= 2 * math.pi
        while angle_error < -math.pi:
            angle_error += 2 * math.pi
        
        # Compute angular velocity (proportional to angle error)
        angular_velocity = self.k_angular * angle_error
        
        # Limit angular velocity
        angular_velocity = max(-self.max_angular_speed, 
                              min(self.max_angular_speed, angular_velocity))
        
        # Compute linear velocity (proportional to distance, but reduced if large angle error)
        # This ensures we slow down for sharp turns
        linear_velocity = self.k_linear * distance * (1 - abs(angle_error) / math.pi)
        
        # Slow down as we approach the end of the path
        if self.current_path_index >= len(self.current_path) - 3:
            slow_factor = distance / self.slow_down_distance if self.slow_down_distance > 0 else 1.0
            linear_velocity *= min(1.0, slow_factor)
        
        # Limit linear velocity
        linear_velocity = max(0, min(self.max_linear_speed, linear_velocity))
        
        return linear_velocity, angular_velocity
    
    async def execute_path(self, current_position: Point2D, current_orientation: float):
        """Execute the current path by sending velocity commands"""
        if not self.zenoh_session or not self.cmd_vel_publisher:
            success = await self.initialize()
            if not success:
                return False
        
        if not self.current_path:
            logging.warning("No path to execute")
            return False
        
        self.is_executing = True
        
        try:
            while self.is_executing and not self.is_paused:
                # Get the target point
                target_point = self.get_target_point(current_position)
                
                # If no target point, we've reached the end of the path
                if not target_point:
                    # Send stop command
                    self._publish_velocity(0, 0)
                    self.is_executing = False
                    logging.info("Path execution completed")
                    return True
                
                # Check if we've reached the final target
                if self.current_path_index >= len(self.current_path) - 1:
                    # Calculate distance to final target
                    dx = target_point.x - current_position.x
                    dy = target_point.y - current_position.y
                    distance = math.sqrt(dx*dx + dy*dy)
                    
                    if distance <= self.goal_tolerance:
                        # Send stop command
                        self._publish_velocity(0, 0)
                        self.is_executing = False
                        logging.info("Reached final target")
                        return True
                
                # Compute velocity
                linear_vel, angular_vel = self.compute_velocity(
                    current_position, current_orientation, target_point
                )
                
                # Publish velocity command
                self._publish_velocity(linear_vel, angular_vel)
                
                # Short sleep to avoid flooding the system
                await asyncio.sleep(0.05)
            
            # If we're here, we either paused or stopped execution
            # Send stop command
            self._publish_velocity(0, 0)
            
            return True
            
        except Exception as e:
            logging.error(f"Error during path execution: {e}")
            self._publish_velocity(0, 0)  # Emergency stop
            self.is_executing = False
            return False
    
    def _publish_velocity(self, linear: float, angular: float):
        """Publish velocity command"""
        if not self.cmd_vel_publisher:
            return
        
        # Create Twist message
        twist = geometry_msgs.Twist()
        twist.linear.x = linear
        twist.linear.y = 0.0
        twist.linear.z = 0.0
        twist.angular.x = 0.0
        twist.angular.y = 0.0
        twist.angular.z = angular
        
        # Serialize and publish
        self.cmd_vel_publisher.put(twist.serialize())
    
    def pause(self):
        """Pause path execution"""
        self.is_paused = True
        self._publish_velocity(0, 0)  # Stop when paused
    
    def resume(self):
        """Resume path execution"""
        self.is_paused = False
    
    def stop(self):
        """Stop path execution"""
        self.is_executing = False
        self._publish_velocity(0, 0)  # Stop
    
    def cleanup(self):
        """Clean up resources"""
        self.stop()
        if self.zenoh_session:
            if self.cmd_vel_publisher:
                self.cmd_vel_publisher.undeclare()
            self.zenoh_session.close()
            self.zenoh_session = None 