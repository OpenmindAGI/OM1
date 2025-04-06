import os
import time
import json
import numpy as np
from threading import Thread

from src.simulators.plugins.SimpleMapper import SimpleMapper

class MapGeneratorPlugin:
    """
    Plugin that generates maps for unknown areas during robot exploration.
    Connects with the simulation environment and processes sensor data.
    """
    
    def __init__(self, simulator=None, config=None):
        """
        Initialize the map generator plugin.
        
        Args:
            simulator: The simulator instance
            config: Configuration for the plugin
        """
        self.simulator = simulator
        self.config = config or {}
        
        # Default configuration values
        self.map_size = self.config.get('map_size', 200)
        self.resolution = self.config.get('resolution', 0.05)
        self.robot_radius = self.config.get('robot_radius', 0.3)
        self.update_interval = self.config.get('update_interval', 0.5)  # How often to update the map
        self.visualization_interval = self.config.get('visualization_interval', 1.0)  # How often to update the visualization
        
        # Create the mapper
        self.mapper = SimpleMapper(
            map_size=self.map_size,
            resolution=self.resolution,
            robot_radius=self.robot_radius
        )
        
        # Thread for regular map updates
        self.update_thread = None
        self.running = False
        
        # Timestamp for the session
        self.session_timestamp = int(time.time())
        
        # Initialize maps directory
        self.maps_dir = os.path.join(os.getcwd(), "maps")
        os.makedirs(self.maps_dir, exist_ok=True)
        
        print(f"Map Generator Plugin initialized. Maps will be saved to {self.maps_dir}")
    
    def start(self):
        """Start the mapping process."""
        if self.update_thread is not None and self.update_thread.is_alive():
            print("Map generator is already running.")
            return
        
        self.running = True
        self.update_thread = Thread(target=self._update_loop)
        self.update_thread.daemon = True
        self.update_thread.start()
        
        # Start the visualization in a separate thread
        self.mapper.start_visualization(update_interval=self.visualization_interval)
        
        print("Map generator started.")
    
    def stop(self):
        """Stop the mapping process."""
        self.running = False
        if self.update_thread is not None:
            self.update_thread.join(timeout=1.0)
            self.update_thread = None
        
        # Stop visualization
        self.mapper.stop_visualization()
        
        # Save final map
        self.save_final_map()
        
        print("Map generator stopped.")
    
    def _update_loop(self):
        """Main loop for updating the map based on sensor data."""
        while self.running:
            try:
                # Get robot pose from simulator if available
                if hasattr(self.simulator, 'get_robot_pose'):
                    pose = self.simulator.get_robot_pose()
                    if pose is not None and len(pose) >= 3:
                        self.mapper.update_pose(pose[0], pose[1], pose[2])
                
                # Get laser scan data from simulator if available
                if hasattr(self.simulator, 'get_laser_scan'):
                    scan_data = self.simulator.get_laser_scan()
                    if scan_data is not None:
                        # Extract ranges and angle information
                        ranges = scan_data.get('ranges', [])
                        angle_min = scan_data.get('angle_min', -np.pi)
                        angle_max = scan_data.get('angle_max', np.pi)
                        angle_increment = scan_data.get('angle_increment', 0.01)
                        
                        # Update the map with laser scan data
                        self.mapper.update_map_from_laser_scan(
                            ranges, angle_min, angle_max, angle_increment
                        )
            
            except Exception as e:
                print(f"Error in map generator update loop: {e}")
            
            # Sleep to control update rate
            time.sleep(self.update_interval)
    
    def save_final_map(self):
        """Save the final map after mapping is complete."""
        final_map_filename = f"final_map_{self.session_timestamp}.png"
        self.mapper.save_map(final_map_filename)
        
        # Also save the metadata in a separate file for easy access
        metadata = {
            "timestamp": self.session_timestamp,
            "map_size": self.map_size,
            "resolution": self.resolution,
            "robot_radius": self.robot_radius,
            "map_file": final_map_filename
        }
        
        metadata_path = os.path.join(self.maps_dir, f"metadata_{self.session_timestamp}.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"Final map saved with metadata to {metadata_path}")
    
    def get_current_map(self):
        """
        Get the current map data.
        
        Returns:
            dict: Map data including the occupancy grid and metadata
        """
        return {
            "occupancy_grid": self.mapper.get_map(),
            "resolution": self.resolution,
            "map_size": self.map_size,
            "robot_position": (self.mapper.robot_x, self.mapper.robot_y, self.mapper.robot_theta)
        } 