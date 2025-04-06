# Integrating Map Generation with Gazebo Simulator

This guide explains how to integrate the map generation functionality with the Gazebo simulator in the OM1 project.

## Prerequisites

- Gazebo simulator installed and configured
- OM1 project set up
- Basic understanding of the Gazebo simulator and its interfaces

## Integration Steps

### 1. Create a Gazebo Adapter

Create a class that adapts the Gazebo interfaces to the format expected by the mapping plugin:

```python
# src/simulators/gazebo_mapping_adapter.py
import numpy as np
import zenoh
from src.simulators.plugins.MapGeneratorPlugin import MapGeneratorPlugin
from src.zenoh_idl import sensor_msgs

class GazeboMappingAdapter:
    """
    Adapter class that connects Gazebo simulator with the mapping plugin.
    It handles communication with Gazebo via Zenoh and converts sensor data
    to the format expected by the MapGeneratorPlugin.
    """
    
    def __init__(self, config=None):
        # Initialize Zenoh session
        self.session = zenoh.open()
        
        # Subscribe to laser scan topic
        self.sub_scan = self.session.declare_subscriber(
            "URID/pi/scan",
            lambda sample: self._process_scan(sample)
        )
        
        # Subscribe to robot pose/odometry topic
        self.sub_odom = self.session.declare_subscriber(
            "odom",
            lambda sample: self._process_odom(sample)
        )
        
        # Initialize data storage
        self.latest_scan = None
        self.latest_pose = [0.0, 0.0, 0.0]  # x, y, theta
        
        # Create the mapping plugin
        self.map_generator = MapGeneratorPlugin(self, config)
    
    def _process_scan(self, sample):
        """Process incoming laser scan data"""
        scan = sensor_msgs.LaserScan.deserialize(sample.payload.to_bytes())
        self.latest_scan = {
            'ranges': scan.ranges,
            'angle_min': scan.angle_min,
            'angle_max': scan.angle_max,
            'angle_increment': scan.angle_increment,
            'range_min': scan.range_min,
            'range_max': scan.range_max
        }
    
    def _process_odom(self, sample):
        """Process incoming odometry data"""
        # The exact format of odometry data may vary; adjust as needed
        odom = sensor_msgs.Odometry.deserialize(sample.payload.to_bytes())
        
        position = odom.pose.pose.position
        orientation = odom.pose.pose.orientation
        
        # Extract position
        x = position.x
        y = position.y
        
        # Extract orientation (convert quaternion to euler angle)
        # This is a simplified conversion - only extracting yaw
        qx, qy, qz, qw = orientation.x, orientation.y, orientation.z, orientation.w
        yaw = np.arctan2(2.0 * (qw * qz + qx * qy), 
                         1.0 - 2.0 * (qy * qy + qz * qz))
        
        self.latest_pose = [x, y, yaw]
    
    def get_robot_pose(self):
        """Return the latest robot pose for the mapping plugin"""
        return self.latest_pose
    
    def get_laser_scan(self):
        """Return the latest laser scan for the mapping plugin"""
        return self.latest_scan
    
    def start(self):
        """Start the mapping process"""
        self.map_generator.start()
    
    def stop(self):
        """Stop the mapping process and clean up resources"""
        self.map_generator.stop()
        
        # Clean up Zenoh subscriptions
        self.session.undeclare_subscriber(self.sub_scan)
        self.session.undeclare_subscriber(self.sub_odom)
        self.session.close()
```

### 2. Create an Example Script

Create an example script to run the integration:

```python
# src/simulators/plugins/examples/gazebo_mapping_example.py
#!/usr/bin/env python3
"""
Example script demonstrating how to use the mapping plugin with Gazebo.
Make sure Gazebo is running before starting this script.
"""

import os
import sys
import time
import signal
import argparse

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

from src.simulators.gazebo_mapping_adapter import GazeboMappingAdapter

def signal_handler(sig, frame):
    """Handle Ctrl+C to gracefully shut down"""
    print("\nStopping mapping...")
    if adapter:
        adapter.stop()
    sys.exit(0)

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Generate maps using Gazebo simulator')
    parser.add_argument('--map-size', type=int, default=400,
                        help='Size of the map in cells (default: 400)')
    parser.add_argument('--resolution', type=float, default=0.05,
                        help='Resolution of the map in meters per cell (default: 0.05)')
    parser.add_argument('--robot-radius', type=float, default=0.3,
                        help='Radius of the robot in meters (default: 0.3)')
    parser.add_argument('--duration', type=int, default=0,
                        help='Duration to run the mapping in seconds (0 = indefinite, default: 0)')
    args = parser.parse_args()
    
    # Configure the mapping system
    config = {
        'map_size': args.map_size,
        'resolution': args.resolution,
        'robot_radius': args.robot_radius,
        'update_interval': 0.2,
        'visualization_interval': 0.5
    }
    
    # Setup signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create the adapter and start mapping
    adapter = GazeboMappingAdapter(config)
    adapter.start()
    
    print(f"Mapping started. Maps will be saved to the 'maps' directory.")
    print("Press Ctrl+C to stop mapping and save the final map.")
    
    # Run for a specified duration or indefinitely
    if args.duration > 0:
        time.sleep(args.duration)
        adapter.stop()
        print(f"Mapping completed after {args.duration} seconds.")
    else:
        # Run indefinitely until Ctrl+C
        while True:
            time.sleep(1)
```

### 3. Running with Gazebo

1. Start Gazebo with your robot model:

```bash
# Navigate to the OM1 project root
cd /path/to/OM1

# Start Gazebo (adjust script based on your OS)
./gazebo/macOS.sh  # For macOS
# or
./gazebo/ubuntu.sh  # For Ubuntu
```

2. In a separate terminal, run the mapping example:

```bash
# Navigate to the OM1 project root
cd /path/to/OM1

# Run the mapping example
python src/simulators/plugins/examples/gazebo_mapping_example.py
```

3. You should see a visualization window showing the map being generated in real-time as the robot moves in the Gazebo environment.

4. Press Ctrl+C to stop the mapping process and save the final map.

## Customization

### Adjusting Map Parameters

You can adjust the map parameters via command line arguments:

```bash
python src/simulators/plugins/examples/gazebo_mapping_example.py --map-size 600 --resolution 0.025 --robot-radius 0.25
```

### Adjusting Topic Names

If your Gazebo environment uses different topic names, you'll need to modify the topic names in the `GazeboMappingAdapter` class:

```python
# Example of custom topic names
self.sub_scan = self.session.declare_subscriber(
    "your_robot/laser_scan",  # Replace with your laser scan topic
    lambda sample: self._process_scan(sample)
)

self.sub_odom = self.session.declare_subscriber(
    "your_robot/odom",  # Replace with your odometry topic
    lambda sample: self._process_odom(sample)
)
```

## Tips for Better Mapping

1. **Move slowly**: For best results, move the robot slowly to allow the mapping system to accumulate accurate data.

2. **Explore systematically**: Have the robot explore the environment in a systematic way to ensure complete coverage.

3. **Adjust map resolution**: For larger environments, you might want to use a larger cell size (smaller resolution value) to keep the map size manageable.

4. **Save maps periodically**: For long mapping sessions, the system automatically saves maps periodically, but you can also modify the code to save more frequently if needed. 