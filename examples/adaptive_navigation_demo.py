#!/usr/bin/env python3
"""
Adaptive Navigation Demo (Simplified)

This script demonstrates a simplified version of the adaptive navigation system.
"""

import asyncio
import logging
import sys
import time
from typing import List

# Add src to path if running directly
sys.path.insert(0, "src")

from actions.adaptive_nav.interface import (
    NavigationInput, 
    NavigationOutput, 
    NavigationMode, 
    Point2D
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("adaptive_nav_demo")


class MockAdaptiveNavConnector:
    """
    Mock implementation of the AdaptiveNavConnector for demonstration.
    Simulates path planning and navigation without actual hardware.
    """
    def __init__(self):
        self.grid = MockOccupancyGrid()
        self.planner = MockPathPlanner()
        self.current_position = Point2D(x=0.0, y=0.0)
        
    async def initialize(self):
        """Initialize the navigation system"""
        logger.info("Mock navigation system initialized")
    
    async def invoke(self, args: NavigationInput) -> NavigationOutput:
        """Simulate navigation"""
        logger.info(f"Mock navigation to target: ({args.target.x}, {args.target.y})")
        
        # Simulate planning a path
        path = self.planner.plan_path(
            self.current_position,
            args.target
        )
        
        # Create output
        output = NavigationOutput()
        output.success = True
        output.message = "Mock navigation completed"
        output.path_points = path if path else []
        output.path_length = self._calculate_path_length(path)
        output.obstacles_detected = 0
        
        # Simulate delay for "movement"
        await asyncio.sleep(1)
        
        return output
        
    async def cleanup(self):
        """Clean up resources"""
        logger.info("Mock navigation system cleaned up")
        
    def _calculate_path_length(self, path: List[Point2D]) -> float:
        """Calculate the total length of a path"""
        if len(path) < 2:
            return 0.0
            
        length = 0.0
        for i in range(1, len(path)):
            dx = path[i].x - path[i-1].x
            dy = path[i].y - path[i-1].y
            length += (dx*dx + dy*dy)**0.5
            
        return length


class MockOccupancyGrid:
    """Mock implementation of occupancy grid"""
    def __init__(self):
        self.obstacles = []
        
    def set_obstacle(self, x, y, radius=0.1):
        """Add an obstacle to the grid"""
        self.obstacles.append((x, y, radius))
        logger.info(f"Added mock obstacle at ({x}, {y}) with radius {radius}")


class MockPathPlanner:
    """Mock implementation of path planner"""
    def plan_path(self, start: Point2D, goal: Point2D, social_mode: bool = False) -> List[Point2D]:
        """Generate a simple straight-line path from start to goal"""
        # Just create a simple path with 5 intermediate points
        path = [start]
        
        # Add intermediate points
        for i in range(1, 6):
            t = i / 6.0
            x = start.x + t * (goal.x - start.x)
            y = start.y + t * (goal.y - start.y)
            path.append(Point2D(x=x, y=y))
            
        path.append(goal)
        return path


async def demo_simple_navigation():
    """Demonstrate simple navigation to a target point"""
    logger.info("Starting simple navigation demo")
    
    # Initialize navigation components
    navigator = MockAdaptiveNavConnector()
    await navigator.initialize()
    
    # Create target position
    target = Point2D(x=2.0, y=0.0)
    
    # Create navigation input
    nav_input = NavigationInput(
        mode=NavigationMode.NORMAL,
        target=target,
        avoid_radius=0.5,
        max_speed=0.5
    )
    
    # Execute navigation
    logger.info(f"Navigating to target: ({target.x}, {target.y})")
    result = await navigator.invoke(nav_input)
    
    # Display result
    if result.success:
        logger.info(f"Navigation successful: {result.message}")
        logger.info(f"Path length: {result.path_length:.2f}m")
        logger.info(f"Obstacles detected: {result.obstacles_detected}")
    else:
        logger.error(f"Navigation failed: {result.message}")
    
    # Clean up
    await navigator.cleanup()


async def demo_obstacle_avoidance():
    """Demonstrate navigation with obstacle avoidance"""
    logger.info("Starting obstacle avoidance demo")
    
    # Initialize navigation components
    navigator = MockAdaptiveNavConnector()
    await navigator.initialize()
    
    # Add some simulated obstacles to the map
    for x, y in [
        (1.0, 0.2),
        (1.0, -0.2),
        (1.5, 0.3),
        (1.5, -0.3)
    ]:
        navigator.grid.set_obstacle(x, y, radius=0.15)
    
    # Create target position
    target = Point2D(x=2.0, y=0.0)
    
    # Create navigation input
    nav_input = NavigationInput(
        mode=NavigationMode.SAFE,  # Use safe mode for more conservative navigation
        target=target,
        avoid_radius=0.6,
        max_speed=0.3  # Slower speed for safety
    )
    
    # Execute navigation
    logger.info(f"Navigating to target: ({target.x}, {target.y}) with obstacles")
    result = await navigator.invoke(nav_input)
    
    # Display result
    if result.success:
        logger.info(f"Navigation successful: {result.message}")
        logger.info(f"Path length: {result.path_length:.2f}m")
        logger.info(f"Obstacles detected: {result.obstacles_detected}")
    else:
        logger.error(f"Navigation failed: {result.message}")
    
    # Clean up
    await navigator.cleanup()


async def main():
    """Main entry point for the demo"""
    logger.info("Starting Adaptive Navigation Demo")
    
    try:
        await demo_simple_navigation()
        logger.info("-" * 50)
        await demo_obstacle_avoidance()
    except Exception as e:
        logger.error(f"Demo error: {e}")
    
    logger.info("Demo completed")


if __name__ == "__main__":
    asyncio.run(main()) 