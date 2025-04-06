import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import math
import os
import time
from threading import Thread
import json

class SimpleMapper:
    """
    A simple implementation of an occupancy grid mapping system.
    This class processes laser scan data to build a 2D map of the environment.
    """
    
    def __init__(self, map_size=200, resolution=0.05, robot_radius=0.3, unknown_area_value=0.5):
        """
        Initialize the mapper.
        
        Args:
            map_size (int): Size of the square map in cells
            resolution (float): Resolution of the map in meters per cell
            robot_radius (float): Radius of the robot in meters
            unknown_area_value (float): Value to initialize the map cells with (0.5 is unknown)
        """
        self.map_size = map_size
        self.resolution = resolution
        self.robot_radius = robot_radius
        
        # Create an empty map with all cells set to unknown
        self.map = np.ones((map_size, map_size), dtype=np.float32) * unknown_area_value
        
        # Center of the map (robot's starting position)
        self.center_x = map_size // 2
        self.center_y = map_size // 2
        
        # Current robot position (in map coordinates)
        self.robot_x = self.center_x
        self.robot_y = self.center_y
        self.robot_theta = 0.0  # heading in radians
        
        # Map for visualization
        self.vis_map = None
        
        # Thread for map visualization
        self.vis_thread = None
        self.running = False
        
        # Path of the robot
        self.path = [(self.robot_x, self.robot_y)]
        
        # Create output directory for maps
        self.output_dir = os.path.join(os.getcwd(), "maps")
        os.makedirs(self.output_dir, exist_ok=True)
        
    def update_pose(self, x, y, theta):
        """
        Update the robot's pose.
        
        Args:
            x (float): X-position in meters
            y (float): Y-position in meters
            theta (float): Heading in radians
        """
        # Convert world coordinates to map coordinates
        map_x = self.center_x + int(x / self.resolution)
        map_y = self.center_y + int(y / self.resolution)
        
        self.robot_x = map_x
        self.robot_y = map_y
        self.robot_theta = theta
        
        # Add current position to path
        self.path.append((map_x, map_y))
    
    def update_map_from_laser_scan(self, ranges, angle_min, angle_max, angle_increment):
        """
        Update the map using laser scan data.
        
        Args:
            ranges (list): List of range measurements in meters
            angle_min (float): Start angle of the scan in radians
            angle_max (float): End angle of the scan in radians
            angle_increment (float): Angular distance between measurements in radians
        """
        for i, distance in enumerate(ranges):
            # Skip invalid measurements
            if math.isnan(distance) or distance <= 0:
                continue
            
            # Calculate angle for this measurement
            angle = angle_min + i * angle_increment
            
            # Calculate global angle based on robot orientation
            global_angle = self.robot_theta + angle
            
            # Calculate obstacle position in world coordinates
            obstacle_x = self.robot_x + int((distance * math.cos(global_angle)) / self.resolution)
            obstacle_y = self.robot_y + int((distance * math.sin(global_angle)) / self.resolution)
            
            # Check if the point is within map bounds
            if (0 <= obstacle_x < self.map_size and 0 <= obstacle_y < self.map_size):
                # Mark the obstacle cell (1.0 = occupied)
                self.map[obstacle_y, obstacle_x] = 1.0
                
                # Use Bresenham's line algorithm to update cells between robot and obstacle
                self._update_cells_on_ray(self.robot_x, self.robot_y, obstacle_x, obstacle_y)
    
    def _update_cells_on_ray(self, x0, y0, x1, y1):
        """
        Update cells along a ray from robot to obstacle using Bresenham's line algorithm.
        Marks cells along the ray as free (0.0) except for the end point.
        
        Args:
            x0, y0 (int): Start position (robot)
            x1, y1 (int): End position (obstacle)
        """
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        
        x, y = x0, y0
        while (x != x1 or y != y1):
            # Skip the end point as we've already marked it as an obstacle
            if (x != x1 or y != y1):
                # Mark cell as free space (0.0 = free)
                if 0 <= x < self.map_size and 0 <= y < self.map_size:
                    self.map[y, x] = 0.0
            
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy
    
    def start_visualization(self, update_interval=1.0):
        """
        Start a thread to periodically visualize the map.
        
        Args:
            update_interval (float): Time between updates in seconds
        """
        if self.vis_thread is not None and self.vis_thread.is_alive():
            return
        
        self.running = True
        self.vis_thread = Thread(target=self._visualization_loop, args=(update_interval,))
        self.vis_thread.daemon = True
        self.vis_thread.start()
    
    def stop_visualization(self):
        """Stop the visualization thread."""
        self.running = False
        if self.vis_thread is not None:
            self.vis_thread.join(timeout=1.0)
            self.vis_thread = None
    
    def _visualization_loop(self, update_interval):
        """
        Main loop for map visualization.
        
        Args:
            update_interval (float): Time between updates in seconds
        """
        plt.ion()  # Enable interactive mode
        fig, ax = plt.subplots(figsize=(8, 8))
        
        timestamp = int(time.time())
        map_count = 0
        
        while self.running:
            ax.clear()
            
            # Create custom colormap: gray for unknown, white for free, black for occupied
            colors = [(0, 0, 0), (1, 1, 1), (0.5, 0.5, 0.5)]  # black, white, gray
            cmap = LinearSegmentedColormap.from_list("custom_map", colors, N=3)
            
            # Display the map
            ax.imshow(self.map, cmap=cmap, vmin=0.0, vmax=1.0, origin='lower')
            
            # Plot robot position
            ax.plot(self.robot_x, self.robot_y, 'ro', markersize=10)
            
            # Plot robot heading
            head_len = 10
            dx = head_len * math.cos(self.robot_theta)
            dy = head_len * math.sin(self.robot_theta)
            ax.arrow(self.robot_x, self.robot_y, dx, dy, 
                    head_width=5, head_length=5, fc='r', ec='r')
            
            # Plot robot path
            path_x = [p[0] for p in self.path]
            path_y = [p[1] for p in self.path]
            ax.plot(path_x, path_y, 'b-', linewidth=1)
            
            ax.set_title(f"Simple Occupancy Grid Map")
            plt.draw()
            plt.pause(0.001)
            
            # Save the map occasionally
            if map_count % 10 == 0:
                self.save_map(f"map_{timestamp}_{map_count}.png")
            
            map_count += 1
            time.sleep(update_interval)
        
        plt.close()
    
    def save_map(self, filename=None):
        """
        Save the current map as both an image and a JSON file.
        
        Args:
            filename (str, optional): Name for the map file
        """
        if filename is None:
            timestamp = int(time.time())
            filename = f"map_{timestamp}.png"
        
        file_path = os.path.join(self.output_dir, filename)
        
        # Save as image
        plt.figure(figsize=(10, 10))
        colors = [(0, 0, 0), (1, 1, 1), (0.5, 0.5, 0.5)]  # black, white, gray
        cmap = LinearSegmentedColormap.from_list("custom_map", colors, N=3)
        plt.imshow(self.map, cmap=cmap, vmin=0.0, vmax=1.0, origin='lower')
        plt.colorbar(label='Occupancy (0=Free, 0.5=Unknown, 1=Occupied)')
        plt.title(f"Occupancy Grid Map")
        plt.savefig(file_path)
        plt.close()
        
        # Also save as JSON for potential later use
        json_filename = os.path.splitext(filename)[0] + ".json"
        json_path = os.path.join(self.output_dir, json_filename)
        
        map_data = {
            "map_size": self.map_size,
            "resolution": self.resolution,
            "robot_radius": self.robot_radius,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "robot_x": self.robot_x,
            "robot_y": self.robot_y,
            "robot_theta": self.robot_theta,
            "path": self.path,
            # Convert numpy array to list for JSON serialization
            "map": self.map.tolist()
        }
        
        with open(json_path, 'w') as f:
            json.dump(map_data, f)
        
        print(f"Map saved to {file_path} and {json_path}")
        
    def get_map(self):
        """
        Get the current map.
        
        Returns:
            numpy.ndarray: The occupancy grid map
        """
        return self.map 