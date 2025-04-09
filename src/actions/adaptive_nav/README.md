# Adaptive Navigation System

This module provides adaptive navigation capabilities in complex and dynamic environments for robots in the OM1 ecosystem. It enables robots to safely navigate through human-populated spaces with real-time obstacle avoidance and path adjustments.

## Features

- **Real-time path planning**: Efficiently generate paths in dynamic environments
- **Obstacle avoidance**: Detect and avoid static and moving obstacles 
- **Social navigation**: Respect human social spaces and maintain appropriate distances
- **Multiple navigation modes**: Choose from safe, normal, efficient, social, or follow modes
- **Dynamic replanning**: Automatically replan paths when obstacles appear
- **Visualization tools**: Debug and monitor navigation with real-time visualization
- **Path smoothing**: Generate smooth paths for natural robot movement
- **Performance logging**: Track navigation metrics for optimization

## Usage

### Basic Usage

```python
from actions.adaptive_nav import AdaptiveNav, NavigationInput, Point2D, NavigationMode

# Create navigation input
nav_input = NavigationInput(
    mode=NavigationMode.NORMAL,
    target=Point2D(x=2.5, y=1.0),
    avoid_radius=0.5,
    max_speed=0.5
)

# Execute navigation through the OM1 action system
# This is typically done through the runtime system, not directly
```

### Navigation Modes

- **SAFE**: Prioritizes safety with slower speeds and larger obstacle avoidance margins
- **NORMAL**: Balanced approach for everyday navigation tasks
- **EFFICIENT**: Faster movement with more direct paths, useful for open areas
- **SOCIAL**: Respects human personal space, maintaining appropriate distances
- **FOLLOW**: Optimized for following a person or object

### Integration Examples

#### Using in the Cortex Runtime

The adaptive navigation system integrates with the existing OM1 runtime system:

```python
# Example of how the navigation system is used in the OM1 runtime
nav_command = {
    "type": "adaptive_nav",
    "mode": "normal",
    "target": {"x": 2.5, "y": 1.0},
    "avoid_radius": 0.5
}

await action_orchestrator.promise([nav_command])
```

#### With Human Interaction

```python
# Example of social navigation around humans
nav_input = NavigationInput(
    mode=NavigationMode.SOCIAL,
    target=Point2D(x=2.5, y=1.0),
    avoid_radius=0.7,  # Larger radius for human comfort
    max_speed=0.3      # Slower speed around humans
)
```

## Implementation Details

### Key Components

1. **AdaptiveNavConnector**: Main entry point for navigation functionality
2. **OccupancyGrid**: Maintains a grid representation of the environment
3. **AdaptivePathPlanner**: Plans paths using A* algorithm with extensions
4. **MovementController**: Translates paths to movement commands
5. **HumanAwarenessModule**: Detects and models humans for social navigation
6. **NavigationVisualizer**: Provides visualization for debugging

### Architecture

The navigation system follows this general workflow:

1. Collect sensor data (LIDAR, cameras) to build an environment map
2. Detect obstacles and humans in the environment
3. Plan a path to the target location using A* algorithm
4. Apply path smoothing for natural movement
5. Execute the path by sending velocity commands
6. Continuously monitor for new obstacles
7. Replan when necessary

## Requirements

- ROS2/Zenoh for communication
- LIDAR or other distance sensors for obstacle detection
- Odometry for robot positioning

## Testing

Run the tests to verify the navigation system's functionality:

```bash
pytest tests/actions/adaptive_nav
```

## Future Improvements

- Predictive modeling of human movement
- Integration with semantic mapping for context-aware navigation
- Learning-based path optimization
- Multi-robot coordination 