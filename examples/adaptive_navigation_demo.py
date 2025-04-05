#!/usr/bin/env python3
"""
Adaptive Navigation Demo

This script demonstrates how to use the adaptive navigation system
to navigate a robot through a complex environment with obstacles and humans.
"""

import asyncio
import logging
import math
import sys
import time
from typing import List, Tuple

# Add src to path if running directly
sys.path.insert(0, "src")

from actions.adaptive_nav import (
    AdaptiveNav, 
    NavigationInput, 
    NavigationOutput, 
    NavigationMode, 
    Point2D
)
from actions.adaptive_nav.connector.navigator import AdaptiveNavConnector
from actions.adaptive_nav.connector.movement_controller import MovementController
from actions.adaptive_nav.connector.human_awareness import HumanAwarenessModule
from actions.adaptive_nav.connector.visualization import NavigationVisualizer, NavigationLogger


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("adaptive_nav_demo")


async def demo_simple_navigation():
    """Demonstrate simple navigation to a target point"""
    logger.info("Starting simple navigation demo")
    
    # Initialize navigation components
    navigator = AdaptiveNavConnector()
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
    navigator = AdaptiveNavConnector()
    await navigator.initialize()
    
    # Add some simulated obstacles to the map
    # In a real system, these would come from sensor data
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


async def demo_social_navigation():
    """Demonstrate social navigation around humans"""
    logger.info("Starting social navigation demo")
    
    # Initialize navigation components
    navigator = AdaptiveNavConnector()
    await navigator.initialize()
    
    # Initialize human awareness module
    human_awareness = HumanAwarenessModule()
    await human_awareness.initialize()
    
    # Simulate a human in the environment
    # In a real system, this would come from human detection
    human_position = (1.5, 0.0)
    human_radius = 0.3
    
    # Add human as an obstacle
    navigator.grid.set_obstacle(human_position[0], human_position[1], radius=human_radius)
    
    # Create target position
    target = Point2D(x=2.0, y=0.0)
    
    # Create navigation input
    nav_input = NavigationInput(
        mode=NavigationMode.SOCIAL,  # Use social mode for human-aware navigation
        target=target,
        avoid_radius=0.8,  # Larger radius for social comfort
        max_speed=0.3  # Slower speed around humans
    )
    
    # Execute navigation
    logger.info(f"Navigating to target: ({target.x}, {target.y}) with human awareness")
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
    await human_awareness.cleanup()


async def demo_visualization():
    """Demonstrate visualization of the navigation system"""
    logger.info("Starting visualization demo")
    
    # Initialize navigation components
    navigator = AdaptiveNavConnector()
    await navigator.initialize()
    
    # Initialize visualization
    visualizer = NavigationVisualizer()
    await visualizer.initialize()
    
    # Initialize logger
    logger = NavigationLogger()
    
    # Add some simulated obstacles to the map
    obstacles = []
    for x, y in [
        (1.0, 0.2),
        (1.0, -0.2),
        (1.5, 0.3),
        (1.5, -0.3)
    ]:
        navigator.grid.set_obstacle(x, y, radius=0.15)
        obstacles.append((x, y, 0.15))
    
    # Create target position
    target = Point2D(x=2.0, y=0.0)
    
    # Create navigation input
    nav_input = NavigationInput(
        mode=NavigationMode.NORMAL,
        target=target,
        avoid_radius=0.5,
        max_speed=0.5
    )
    
    # Update visualization
    visualizer.update_obstacles(obstacles)
    visualizer.update_target(target)
    visualizer.update_navigation_mode(nav_input.mode)
    visualizer.update_robot_state((0.0, 0.0), 0.0)
    visualizer.publish_visualization(force=True)
    
    # Log navigation start
    logger.log_start_navigation(target, nav_input.mode)
    
    # Plan path
    start_time = time.time()
    path = navigator.planner.plan_path(
        Point2D(x=0.0, y=0.0),
        target,
        social_mode=(nav_input.mode == NavigationMode.SOCIAL)
    )
    planning_time = time.time() - start_time
    
    # Update visualization with planned path
    visualizer.update_planned_path(path)
    visualizer.publish_visualization(force=True)
    
    # Log path planning
    path_length = 0.0
    if len(path) > 1:
        for i in range(1, len(path)):
            dx = path[i].x - path[i-1].x
            dy = path[i].y - path[i-1].y
            path_length += math.sqrt(dx*dx + dy*dy)
    
    logger.log_path_planning(path_length, path, planning_time)
    
    # Simulate robot moving along the path
    for i, point in enumerate(path):
        # Update robot position
        visualizer.update_robot_state((point.x, point.y), 0.0)
        visualizer.publish_visualization()
        
        # Log position update
        logger.log_position_update(point)
        
        # Simulate obstacle detection
        if i == len(path) // 2:
            logger.log_obstacle_detected((1.0, 0.2), 0.4)
        
        # Wait a bit to simulate movement
        await asyncio.sleep(0.2)
    
    # Log navigation completion
    logger.log_navigation_complete(True, time.time() - start_time, "Navigation completed successfully")
    
    # Print navigation stats
    stats = logger.get_navigation_stats()
    logger.info("Navigation Statistics:")
    for key, value in stats.items():
        logger.info(f"  {key}: {value}")
    
    # Save log
    logger.save_log()
    
    # Clean up
    await navigator.cleanup()
    visualizer.cleanup()


async def main():
    """Run all demos"""
    try:
        await demo_simple_navigation()
        await asyncio.sleep(1)
        
        await demo_obstacle_avoidance()
        await asyncio.sleep(1)
        
        await demo_social_navigation()
        await asyncio.sleep(1)
        
        await demo_visualization()
        
    except KeyboardInterrupt:
        logger.info("Demo interrupted by user")
    except Exception as e:
        logger.error(f"Error in demo: {e}")
    finally:
        logger.info("Demo completed")


if __name__ == "__main__":
    asyncio.run(main()) 