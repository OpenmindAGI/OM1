# Map Generation for Unknown Areas

This directory contains examples demonstrating how to use the mapping functionality for unknown areas in the OM1 project.

## Overview

The map generation system allows robots to create 2D occupancy grid maps of their environment while exploring unknown areas. This is accomplished by processing sensor data (primarily from LIDAR/laser scanners) and updating an occupancy grid map in real-time.

## Features

- Real-time occupancy grid mapping
- Visualization of the map as it's being created
- Map saving to both image (PNG) and JSON formats
- Simple integration with existing simulator interfaces

## Components

The mapping system consists of two main components:

1. **SimpleMapper**: The core mapping algorithm that processes laser scan data to build an occupancy grid map.
2. **MapGeneratorPlugin**: A plugin that connects the mapping algorithm with the simulator environment.

## Requirements

- Python 3.10+
- NumPy
- Matplotlib
- A simulator that provides robot pose and laser scan data

## Usage

### Basic Usage

```python
from src.simulators.plugins.MapGeneratorPlugin import MapGeneratorPlugin

# Create and configure the map generator plugin
config = {
    'map_size': 400,  # cells
    'resolution': 0.05,  # meters per cell
    'robot_radius': 0.3,  # meters
    'update_interval': 0.2,  # seconds between map updates
    'visualization_interval': 0.5  # seconds between visualization updates
}

# Initialize with your simulator
map_generator = MapGeneratorPlugin(simulator, config)

# Start the mapping process
map_generator.start()

# ... (robot explores the environment) ...

# When finished, stop the mapping process
map_generator.stop()  # This will save a final map
```

### Running the Example

The example script `mapping_example.py` demonstrates how to use the mapping system with a mock simulator:

```bash
# Navigate to the root of the OM1 project
cd /path/to/OM1

# Run the example
python src/simulators/plugins/examples/mapping_example.py
```

The example will:
1. Create a mock environment with random obstacles
2. Simulate a robot exploring this environment
3. Generate and visualize a map of the environment in real-time
4. Save the final map to the `maps/` directory when completed

## Simulator Integration

To integrate the mapping system with your own simulator, ensure your simulator provides the following methods:

- `get_robot_pose()`: Should return a list `[x, y, theta]` with the robot's position and orientation
- `get_laser_scan()`: Should return a dictionary with the following keys:
  - `ranges`: List of distance measurements in meters
  - `angle_min`: Start angle of the scan in radians
  - `angle_max`: End angle of the scan in radians
  - `angle_increment`: Angular distance between measurements in radians

## Output

The mapping system generates two types of output files in the `maps/` directory:

1. **PNG Images**: Visual representations of the map where:
   - Black: Occupied cells
   - White: Free cells
   - Gray: Unknown cells

2. **JSON Files**: Structured data containing:
   - Occupancy grid information
   - Map metadata (size, resolution, etc.)
   - Robot path
   - Timestamp information 