# Mapper Agent

This agent generates maps of unknown areas by exploring and navigating through the environment. It's a basic implementation that satisfies the requirements specified in [Issue #181](https://github.com/OpenmindAGI/OM1/issues/181).

## Features

- Generates maps when exploring unknown areas
- Uses simulated lidar-like sensors to detect obstacles
- Automatically visualizes and saves map images during exploration
- Supports basic movement commands (forward, backward, turn)
- Builds occupancy grid maps (free space, obstacles, unknown areas)

## Running the Agent

You can run the mapper agent using the following command:

```bash
uv run src/run.py mapper
```

This will start the agent with the configuration defined in `config/mapper.json5`.

## Implementation Details

The mapper agent uses:

1. **MapSimulator**: A simulator that handles the map generation, robot movement, and visualization
2. **OpenAI LLM**: Processes commands and helps the agent navigate intelligently

The agent moves through the environment by:
- Detecting obstacles with simulated sensors
- Updating its internal map representation
- Making decisions about where to explore next
- Visualizing the map at regular intervals

## Map Visualization

The agent generates map visualizations in the `map_output` directory. These visualizations show:
- Unknown areas (gray)
- Free space (white)
- Obstacles (black)
- Robot position (blue circle)
- Robot orientation (red line)

## Commands

The agent understands the following commands:

- `move forward X` - Move forward X meters
- `move backward X` - Move backward X meters
- `turn X` - Rotate X degrees (positive = right, negative = left)

These commands will be automatically processed by the MapSimulator to update the robot's position and orientation. 