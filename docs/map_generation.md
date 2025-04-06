# Map Generation for Unknown Areas

## Overview

This module enables robots to generate maps of unknown areas during exploration. Using sensor data (primarily from LIDAR or laser scanners), the robot can build an occupancy grid map of its environment in real-time, visualize it, and save it for later use.

## Key Features

1. **Real-time Mapping**: Updates the map in real-time as the robot explores the environment.
2. **Occupancy Grid Implementation**: Uses a standard occupancy grid representation where:
   - 0.0 = Free space
   - 0.5 = Unknown area
   - 1.0 = Occupied space (obstacle)
3. **Visualization**: Provides real-time visualization of the map as it's being generated.
4. **Map Storage**: Saves maps in both image (PNG) and data (JSON) formats.
5. **Integration Options**: Can be used with both simulated environments (like Gazebo) and real robots.

## Architecture

The mapping system consists of the following components:

1. **SimpleMapper**: Core mapping algorithm that converts sensor data into an occupancy grid.
2. **MapGeneratorPlugin**: Plugin that connects the mapper with a simulator or robot interface.
3. **GazeboMappingAdapter**: Adapter for connecting with the Gazebo simulator.

## Usage

### Basic Usage with a Simulator

```python
from src.simulators.plugins.MapGeneratorPlugin import MapGeneratorPlugin

# Create and configure the map generator
config = {
    'map_size': 400,       # Size in cells
    'resolution': 0.05,    # Meters per cell
    'robot_radius': 0.3    # Robot radius in meters
}

# Initialize with your simulator
map_generator = MapGeneratorPlugin(simulator, config)

# Start the mapping process
map_generator.start()

# ... robot explores environment ...

# When finished, stop the mapping process
map_generator.stop()  # This will save the final map
```

### With Gazebo Simulator

```bash
# Start Gazebo
./gazebo/macOS.sh  # or ubuntu.sh

# In another terminal, run the mapping example
python src/simulators/plugins/examples/gazebo_mapping_example.py
```

## Example Scripts

The repository includes several example scripts:

1. **mapping_example.py**: Demonstrates mapping with a mock simulator.
2. **gazebo_mapping_example.py**: Shows how to use mapping with the Gazebo simulator.

## Output

The mapping system generates:

1. **PNG Images**: Visual representation of the map.
2. **JSON Files**: Data representation that can be loaded later.

Maps are saved to the `maps/` directory in the project root.

## Integration with Other Systems

The mapping system is designed to be modular and can be integrated with:

1. **Navigation Systems**: Use the generated maps for path planning.
2. **SLAM Systems**: Combine with localization for more accurate mapping.
3. **Robot Control**: Use the map information to guide exploration strategies.

## Customization

### Map Parameters

- **map_size**: Number of cells in the map (square map)
- **resolution**: Size of each cell in meters
- **robot_radius**: Radius of the robot in meters
- **update_interval**: How often to update the map
- **visualization_interval**: How often to update the visualization

### Example Configuration

```python
config = {
    'map_size': 600,            # Larger map
    'resolution': 0.025,        # Higher resolution
    'robot_radius': 0.25,       # Smaller robot
    'update_interval': 0.1,     # Faster updates
    'visualization_interval': 0.3
}
```

## Implementation Details

### Map Update Process

1. The robot receives sensor data (laser scans)
2. For each reading:
   - Calculate the position of detected obstacles
   - Mark obstacle cells as occupied (1.0)
   - Mark cells between the robot and obstacles as free (0.0)
   - Leave unseen cells as unknown (0.5)

### Ray Casting

The system uses Bresenham's line algorithm to perform ray casting between the robot and detected obstacles.

### Thread Management

The mapping system runs in separate threads to avoid blocking the main simulation or robot control:
- One thread for map updates
- One thread for visualization 