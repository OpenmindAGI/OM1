#!/usr/bin/env python3
"""
Example script demonstrating how to use the MapGeneratorPlugin.

This script creates a simple mock simulator with simulated laser scan data
and shows how the plugin can be used to generate maps of unknown areas.
"""

import os
import sys
import time
import numpy as np
import math
import random
from threading import Thread

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

from src.simulators.plugins.MapGeneratorPlugin import MapGeneratorPlugin


class MockSimulator:
    """
    A simple mock simulator that provides pose and laser scan data for testing.
    """
    
    def __init__(self):
        # Initial pose: x, y, theta
        self.pose = [0.0, 0.0, 0.0]
        
        # Create a simple map with some obstacles (just for simulation purposes)
        # 0 = free space, 1 = obstacle
        self.map_size = 20.0  # meters
        self.obstacle_map = self._create_mock_map()
        
        # Laser scanner parameters
        self.scan_range_max = 5.0  # Maximum range in meters
        self.scan_angle_min = -math.pi  # Minimum angle in radians
        self.scan_angle_max = math.pi  # Maximum angle in radians
        self.scan_angle_increment = math.pi / 180  # 1 degree in radians
        
        # Movement parameters
        self.linear_velocity = 0.2  # m/s
        self.angular_velocity = 0.1  # rad/s
        
        # Thread for simulating robot movement
        self.movement_thread = None
        self.running = False
    
    def _create_mock_map(self):
        """Create a mock map with obstacles."""
        # Simple maze-like environment
        size = 100  # 100x100 grid
        grid = np.zeros((size, size))
        
        # Add outer walls
        grid[0, :] = 1
        grid[-1, :] = 1
        grid[:, 0] = 1
        grid[:, -1] = 1
        
        # Add some inner walls/obstacles (randomly)
        for _ in range(10):
            # Random wall position and length
            x = random.randint(10, size-10)
            y = random.randint(10, size-10)
            length = random.randint(5, 20)
            
            # Horizontal or vertical wall
            if random.choice([True, False]):
                # Horizontal wall
                grid[x:x+length, y] = 1
            else:
                # Vertical wall
                grid[x, y:y+length] = 1
        
        return grid
    
    def start_movement(self):
        """Start the simulated robot movement."""
        if self.movement_thread is not None and self.movement_thread.is_alive():
            return
        
        self.running = True
        self.movement_thread = Thread(target=self._movement_loop)
        self.movement_thread.daemon = True
        self.movement_thread.start()
    
    def stop_movement(self):
        """Stop the simulated robot movement."""
        self.running = False
        if self.movement_thread is not None:
            self.movement_thread.join(timeout=1.0)
            self.movement_thread = None
    
    def _movement_loop(self):
        """Simulate robot movement in the environment."""
        while self.running:
            # Simple wall following with random turns
            if self._check_collision(0.5):  # Check for nearby obstacles
                # Turn away from obstacle
                turn_angle = random.uniform(math.pi/4, math.pi/2)
                if random.choice([True, False]):
                    turn_angle = -turn_angle
                
                # Apply turn
                self.pose[2] += turn_angle
                
                # Normalize angle to -π to π
                self.pose[2] = math.atan2(math.sin(self.pose[2]), math.cos(self.pose[2]))
            else:
                # Move forward with slight random rotation
                distance = self.linear_velocity * 0.1  # 0.1 seconds of movement
                angle_change = random.uniform(-0.05, 0.05)
                
                # Update pose
                self.pose[0] += distance * math.cos(self.pose[2])
                self.pose[1] += distance * math.sin(self.pose[2])
                self.pose[2] += angle_change
                
                # Normalize angle
                self.pose[2] = math.atan2(math.sin(self.pose[2]), math.cos(self.pose[2]))
            
            # Sleep to control update rate
            time.sleep(0.1)
    
    def _check_collision(self, distance_threshold):
        """Check if there's an obstacle within distance_threshold meters."""
        scan = self.get_laser_scan()
        
        # Check if any scan reading is less than threshold
        for r in scan['ranges']:
            if r < distance_threshold:
                return True
        
        return False
    
    def get_robot_pose(self):
        """Return the current robot pose: [x, y, theta]."""
        return self.pose
    
    def get_laser_scan(self):
        """
        Simulate a laser scan at the robot's current position.
        
        Returns:
            dict: Laser scan data including ranges and angle information
        """
        num_rays = int((self.scan_angle_max - self.scan_angle_min) / self.scan_angle_increment) + 1
        ranges = []
        
        for i in range(num_rays):
            # Calculate angle for this ray
            angle = self.scan_angle_min + i * self.scan_angle_increment
            
            # Calculate global angle
            global_angle = self.pose[2] + angle
            
            # Simulate raycasting
            ray_range = self._simulate_raycast(global_angle)
            ranges.append(ray_range)
        
        return {
            'ranges': ranges,
            'angle_min': self.scan_angle_min,
            'angle_max': self.scan_angle_max,
            'angle_increment': self.scan_angle_increment,
            'range_min': 0.1,
            'range_max': self.scan_range_max
        }
    
    def _simulate_raycast(self, angle):
        """
        Simulate a raycast from the robot's position in the given direction.
        
        Args:
            angle (float): Global angle for the ray in radians
            
        Returns:
            float: Distance to the nearest obstacle in this direction
        """
        # Start at robot position
        x, y = self.pose[0], self.pose[1]
        
        # Calculate ray direction
        dx = math.cos(angle)
        dy = math.sin(angle)
        
        # Step size for ray (small for accuracy)
        step_size = 0.1  # meters
        
        # Raycast until we hit something or reach max range
        distance = 0.0
        while distance < self.scan_range_max:
            # Update position along ray
            x += dx * step_size
            y += dy * step_size
            distance += step_size
            
            # Convert world coordinates to grid coordinates
            grid_x = int((x + self.map_size/2) / self.map_size * self.obstacle_map.shape[0])
            grid_y = int((y + self.map_size/2) / self.map_size * self.obstacle_map.shape[1])
            
            # Check if out of bounds
            if (grid_x < 0 or grid_x >= self.obstacle_map.shape[0] or 
                grid_y < 0 or grid_y >= self.obstacle_map.shape[1]):
                return self.scan_range_max
            
            # Check if we hit an obstacle
            if self.obstacle_map[grid_x, grid_y] == 1:
                return distance
        
        # No obstacle found within range
        return self.scan_range_max


def main():
    """Main function to run the example."""
    try:
        print("Starting mapping example...")
        
        # Create the mock simulator
        simulator = MockSimulator()
        
        # Create and configure the map generator plugin
        config = {
            'map_size': 400,  # cells
            'resolution': 0.05,  # meters per cell
            'robot_radius': 0.3,  # meters
            'update_interval': 0.2,  # seconds between map updates
            'visualization_interval': 0.5  # seconds between visualization updates
        }
        map_generator = MapGeneratorPlugin(simulator, config)
        
        # Start the mapping process
        map_generator.start()
        
        # Start the simulated robot movement
        simulator.start_movement()
        
        # Run the example for 60 seconds
        print("Mapping in progress. Press Ctrl+C to stop...")
        time.sleep(60)
        
    except KeyboardInterrupt:
        print("\nStopping example...")
    
    finally:
        # Clean up
        simulator.stop_movement()
        map_generator.stop()
        print("Example complete. Maps have been saved to the 'maps' directory.")


if __name__ == "__main__":
    main() 