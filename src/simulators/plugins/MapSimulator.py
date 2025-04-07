import logging
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import os
import time
from typing import List, Tuple

from llm.output_model import Command
from simulators.base import Simulator, SimulatorConfig


class MapSimulator(Simulator):
    """
    Map generation simulator for unknown areas.
    
    This simulator generates a map as the agent explores an unknown area.
    It tracks the robot's position and builds an occupancy grid map.
    """

    def __init__(self, config: SimulatorConfig):
        """
        Initialize the map simulator with configuration.
        
        Parameters
        ----------
        config : SimulatorConfig
            Configuration for the map simulator including map_size, resolution, etc.
        """
        super().__init__(config)
        self.map_size = getattr(config, "map_size", 400)
        self.resolution = getattr(config, "resolution", 0.05)
        self.robot_radius = getattr(config, "robot_radius", 0.3)
        self.update_interval = getattr(config, "update_interval", 0.2)
        self.visualization_interval = getattr(config, "visualization_interval", 0.5)
        self.simulation_duration = getattr(config, "simulation_duration", 60)
        
        # Initialize map as an occupancy grid (0 = unknown, 1 = free, 2 = occupied)
        self.map = np.zeros((self.map_size, self.map_size))
        
        # Robot position (center of the map initially)
        self.robot_position = (self.map_size // 2, self.map_size // 2)
        self.robot_orientation = 0  # radians, 0 is east, pi/2 is north
        
        # Create a folder for map visualizations
        self.output_dir = "map_output"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Track the last update and visualization times
        self.last_update_time = time.time()
        self.last_viz_time = time.time()
        
        # Create environment with some obstacles
        self._create_environment()
        
        # First visualization
        self._visualize_map()
        
        logging.info("MapSimulator initialized")

    def _create_environment(self):
        """Create a simulated environment with obstacles."""
        # Define the edges of the map as obstacles
        border_width = 10
        self.map[0:border_width, :] = 2  # Top edge
        self.map[-border_width:, :] = 2  # Bottom edge
        self.map[:, 0:border_width] = 2  # Left edge
        self.map[:, -border_width:] = 2  # Right edge
        
        # Add some random obstacles
        np.random.seed(42)  # for reproducibility
        num_obstacles = 20
        for _ in range(num_obstacles):
            x = np.random.randint(border_width, self.map_size - border_width)
            y = np.random.randint(border_width, self.map_size - border_width)
            radius = np.random.randint(5, 20)
            
            # Create circular obstacle
            for i in range(max(0, x - radius), min(self.map_size, x + radius)):
                for j in range(max(0, y - radius), min(self.map_size, y + radius)):
                    if (i - x) ** 2 + (j - y) ** 2 <= radius ** 2:
                        self.map[i, j] = 2  # Occupied
        
        # Clear the area around the robot's starting position
        robot_clear_radius = int(self.robot_radius / self.resolution) + 5
        rx, ry = self.robot_position
        for i in range(max(0, rx - robot_clear_radius), min(self.map_size, rx + robot_clear_radius)):
            for j in range(max(0, ry - robot_clear_radius), min(self.map_size, ry + robot_clear_radius)):
                if (i - rx) ** 2 + (j - ry) ** 2 <= robot_clear_radius ** 2:
                    self.map[i, j] = 1  # Free space around robot
    
    def _visualize_map(self):
        """Visualize the current state of the map."""
        plt.figure(figsize=(10, 10))
        
        # Create a custom colormap: unknown=gray, free=white, occupied=black
        colors = [(0.7, 0.7, 0.7), (1, 1, 1), (0, 0, 0)]  # gray, white, black
        cmap = LinearSegmentedColormap.from_list("map_cmap", colors, N=3)
        
        plt.imshow(self.map, cmap=cmap, vmin=0, vmax=2)
        
        # Plot the robot position and orientation
        robot_size = int(self.robot_radius / self.resolution)
        rx, ry = self.robot_position
        dx = robot_size * np.cos(self.robot_orientation)
        dy = robot_size * np.sin(self.robot_orientation)
        
        # Draw robot as a circle
        circle = plt.Circle((ry, rx), robot_size, color='blue', alpha=0.7)
        plt.gca().add_patch(circle)
        
        # Draw robot orientation as a line
        plt.plot([ry, ry + dy], [rx, rx + dx], 'r-', linewidth=2)
        
        plt.title("Generated Map")
        plt.axis('off')
        
        # Save the map visualization
        map_filename = os.path.join(self.output_dir, f"map_{int(time.time())}.png")
        plt.savefig(map_filename)
        plt.close()
        
        logging.info(f"Map visualization saved to {map_filename}")
    
    def _update_map(self, robot_position: Tuple[int, int], orientation: float):
        """
        Update the map based on the robot's position and orientation.
        
        Parameters
        ----------
        robot_position : Tuple[int, int]
            The robot's position as (x, y) coordinates
        orientation : float
            The robot's orientation in radians
        """
        # Simulate a lidar-like sensor with 16 rays
        num_rays = 16
        max_range = int(5.0 / self.resolution)  # 5 meters max range
        
        rx, ry = robot_position
        
        # Cast rays in different directions
        for i in range(num_rays):
            angle = orientation + i * (2 * np.pi / num_rays)
            dx = np.cos(angle)
            dy = np.sin(angle)
            
            # Trace the ray
            for dist in range(1, max_range):
                x = int(rx + dist * dx)
                y = int(ry + dist * dy)
                
                # Check if we're inside the map
                if 0 <= x < self.map_size and 0 <= y < self.map_size:
                    # If we hit an obstacle, stop the ray
                    if self.map[x, y] == 2:  # Occupied
                        break
                    else:
                        # Mark as free space
                        self.map[x, y] = 1
                else:
                    # We've gone outside the map
                    break
    
    def _process_move_command(self, value: str):
        """
        Process a move command from the LLM.
        
        Parameters
        ----------
        value : str
            The move command value, expecting format like "forward 1.0" or "turn 90"
        """
        try:
            parts = value.split()
            if len(parts) >= 2:
                direction = parts[0].lower()
                magnitude = float(parts[1])
                
                rx, ry = self.robot_position
                
                # Handle different move commands
                if direction == "forward":
                    distance = int(magnitude / self.resolution)
                    new_x = rx + int(distance * np.cos(self.robot_orientation))
                    new_y = ry + int(distance * np.sin(self.robot_orientation))
                    
                    # Check if the new position is valid (not an obstacle)
                    if (0 <= new_x < self.map_size and 0 <= new_y < self.map_size and 
                        self.map[new_x, new_y] != 2):  # Not occupied
                        self.robot_position = (new_x, new_y)
                
                elif direction == "backward":
                    distance = int(magnitude / self.resolution)
                    new_x = rx - int(distance * np.cos(self.robot_orientation))
                    new_y = ry - int(distance * np.sin(self.robot_orientation))
                    
                    # Check if the new position is valid (not an obstacle)
                    if (0 <= new_x < self.map_size and 0 <= new_y < self.map_size and 
                        self.map[new_x, new_y] != 2):  # Not occupied
                        self.robot_position = (new_x, new_y)
                
                elif direction == "turn":
                    # Convert degrees to radians
                    angle_change = np.radians(magnitude)
                    self.robot_orientation = (self.robot_orientation + angle_change) % (2 * np.pi)
                
                logging.info(f"Robot moved: {direction} {magnitude}, new position: {self.robot_position}, orientation: {np.degrees(self.robot_orientation):.2f} degrees")
            else:
                logging.warning(f"Invalid move command format: {value}")
        except Exception as e:
            logging.error(f"Error processing move command: {e}")
    
    def sim(self, commands: List[Command]) -> None:
        """
        Process commands from the LLM.
        
        Parameters
        ----------
        commands : List[Command]
            List of commands to process
        """
        for command in commands:
            if command.type == "move":
                self._process_move_command(command.value)
            elif command.type == "speak":
                logging.info(f"Robot says: {command.value}")
            else:
                logging.warning(f"Unknown command type: {command.type}")
    
    def tick(self) -> None:
        """Run one tick of the simulator."""
        current_time = time.time()
        
        # Update the map at regular intervals
        if current_time - self.last_update_time >= self.update_interval:
            self._update_map(self.robot_position, self.robot_orientation)
            self.last_update_time = current_time
        
        # Visualize the map at regular intervals
        if current_time - self.last_viz_time >= self.visualization_interval:
            self._visualize_map()
            self.last_viz_time = current_time 