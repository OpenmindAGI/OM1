import asyncio
import logging
import math
import time
from typing import List, Optional, Dict, Set, Tuple
import numpy as np
from dataclasses import dataclass, field
import zenoh

from actions.adaptive_nav.interface import (
    AdaptiveNav, 
    NavigationInput, 
    NavigationOutput, 
    Point2D, 
    NavigationMode
)
from actions.base import ActionConnector
from providers.io_provider import IOProvider
from zenoh_idl import sensor_msgs


@dataclass
class GridCell:
    """Represents a cell in the navigation grid"""
    x: int
    y: int
    cost: float = 0.0
    occupied: bool = False
    visited: bool = False
    parent: Optional[Tuple[int, int]] = None
    
    def __hash__(self):
        return hash((self.x, self.y))
    
    def __eq__(self, other):
        if not isinstance(other, GridCell):
            return False
        return self.x == other.x and self.y == other.y


class OccupancyGrid:
    """Simple occupancy grid for navigation"""
    def __init__(self, width: int = 20, height: int = 20, resolution: float = 0.1):
        self.width = width  # Grid width in cells
        self.height = height  # Grid height in cells
        self.resolution = resolution  # Meters per cell
        self.origin_x = -width * resolution / 2  # Center the grid
        self.origin_y = -height * resolution / 2
        self.grid: Dict[Tuple[int, int], GridCell] = {}
        self.obstacles: Set[Tuple[int, int]] = set()
        
        # Initialize grid
        for x in range(width):
            for y in range(height):
                self.grid[(x, y)] = GridCell(x=x, y=y)
    
    def world_to_grid(self, x: float, y: float) -> Tuple[int, int]:
        """Convert world coordinates to grid coordinates"""
        grid_x = int((x - self.origin_x) / self.resolution)
        grid_y = int((y - self.origin_y) / self.resolution)
        # Ensure we're within grid bounds
        grid_x = max(0, min(grid_x, self.width - 1))
        grid_y = max(0, min(grid_y, self.height - 1))
        return grid_x, grid_y
    
    def grid_to_world(self, grid_x: int, grid_y: int) -> Tuple[float, float]:
        """Convert grid coordinates to world coordinates"""
        world_x = grid_x * self.resolution + self.origin_x
        world_y = grid_y * self.resolution + self.origin_y
        return world_x, world_y
    
    def set_obstacle(self, x: float, y: float, radius: float = 0.1):
        """Mark cells within radius as obstacles"""
        grid_x, grid_y = self.world_to_grid(x, y)
        radius_cells = math.ceil(radius / self.resolution)
        
        for dx in range(-radius_cells, radius_cells + 1):
            for dy in range(-radius_cells, radius_cells + 1):
                # Check if the cell is within the circular radius
                if dx*dx + dy*dy <= radius_cells*radius_cells:
                    cell_x, cell_y = grid_x + dx, grid_y + dy
                    if 0 <= cell_x < self.width and 0 <= cell_y < self.height:
                        cell_key = (cell_x, cell_y)
                        self.grid[cell_key].occupied = True
                        self.grid[cell_key].cost = float('inf')
                        self.obstacles.add(cell_key)
    
    def clear_obstacles(self):
        """Clear all obstacles from the grid"""
        for key in self.obstacles:
            self.grid[key].occupied = False
            self.grid[key].cost = 0.0
        self.obstacles.clear()


class AdaptivePathPlanner:
    """Implements adaptive path planning using A* algorithm"""
    def __init__(self, occupancy_grid: OccupancyGrid):
        self.grid = occupancy_grid
        self.directions = [
            (0, 1), (1, 0), (0, -1), (-1, 0),  # 4-connected
            (1, 1), (-1, 1), (1, -1), (-1, -1)  # 8-connected
        ]
    
    def heuristic(self, a: Tuple[int, int], b: Tuple[int, int]) -> float:
        """Calculate heuristic (Euclidean distance)"""
        return math.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2)
    
    def plan_path(self, start: Point2D, goal: Point2D, social_mode: bool = False) -> List[Point2D]:
        """Plan a path from start to goal using A* algorithm"""
        # Convert world coordinates to grid
        start_grid = self.grid.world_to_grid(start.x, start.y)
        goal_grid = self.grid.world_to_grid(goal.x, goal.y)
        
        # Reset visited status
        for cell in self.grid.grid.values():
            cell.visited = False
            cell.parent = None
        
        # Check if goal is in obstacle
        if self.grid.grid[goal_grid].occupied:
            logging.warning("Goal position is in an obstacle!")
            return []
            
        # A* algorithm
        open_set = {start_grid}
        closed_set = set()
        g_score = {start_grid: 0}
        f_score = {start_grid: self.heuristic(start_grid, goal_grid)}
        
        while open_set:
            # Find node with lowest f_score
            current = min(open_set, key=lambda pos: f_score.get(pos, float('inf')))
            
            if current == goal_grid:
                # Path found, reconstruct it
                path = []
                while current:
                    world_x, world_y = self.grid.grid_to_world(current[0], current[1])
                    path.append(Point2D(x=world_x, y=world_y))
                    parent_cell = self.grid.grid[current].parent
                    current = parent_cell
                return path[::-1]  # Reverse to get path from start to goal
            
            open_set.remove(current)
            closed_set.add(current)
            
            # Check all neighbors
            for dx, dy in self.directions:
                neighbor = (current[0] + dx, current[1] + dy)
                
                # Skip if out of bounds
                if (neighbor[0] < 0 or neighbor[0] >= self.grid.width or 
                    neighbor[1] < 0 or neighbor[1] >= self.grid.height):
                    continue
                
                # Skip if in closed set or is an obstacle
                if neighbor in closed_set or self.grid.grid[neighbor].occupied:
                    continue
                
                # Calculate movement cost (diagonal moves cost more)
                move_cost = 1.0 if dx == 0 or dy == 0 else 1.4
                
                # Add social cost if in social mode (avoid getting too close to obstacles)
                if social_mode:
                    # Check proximity to obstacles and add cost
                    for ox, oy in self.grid.obstacles:
                        dist = math.sqrt((neighbor[0] - ox)**2 + (neighbor[1] - oy)**2)
                        if dist < 5:  # 5 cells ~ 0.5m with 0.1m resolution
                            # Inverse square law for social cost
                            move_cost += 2.0 / (dist + 0.1)**2
                
                # Calculate tentative g_score
                tentative_g = g_score.get(current, float('inf')) + move_cost
                
                if neighbor not in open_set:
                    open_set.add(neighbor)
                elif tentative_g >= g_score.get(neighbor, float('inf')):
                    continue
                
                # This path is better, record it
                self.grid.grid[neighbor].parent = current
                g_score[neighbor] = tentative_g
                f_score[neighbor] = tentative_g + self.heuristic(neighbor, goal_grid)
        
        # No path found
        logging.warning("No path found from start to goal")
        return []
    
    def smooth_path(self, path: List[Point2D]) -> List[Point2D]:
        """Apply path smoothing to reduce jagged movements"""
        if len(path) <= 2:
            return path
            
        # Simple path smoothing using a moving average
        smoothed = [path[0]]  # Keep the start point
        
        for i in range(1, len(path) - 1):
            # Average with neighbors
            avg_x = (path[i-1].x + path[i].x + path[i+1].x) / 3
            avg_y = (path[i-1].y + path[i].y + path[i+1].y) / 3
            smoothed.append(Point2D(x=avg_x, y=avg_y))
            
        smoothed.append(path[-1])  # Keep the end point
        return smoothed


class AdaptiveNavConnector(ActionConnector[NavigationOutput]):
    """
    Connector for adaptive navigation in complex environments.
    
    Implements real-time path planning with obstacle avoidance capabilities.
    """
    def __init__(self):
        super().__init__()
        self.io_provider = IOProvider()
        
        # Initialize occupancy grid for mapping
        self.grid = OccupancyGrid(width=100, height=100, resolution=0.05)
        self.planner = AdaptivePathPlanner(self.grid)
        
        # Robot state
        self.current_position = Point2D(x=0.0, y=0.0)
        self.current_orientation = 0.0  # Radians
        self.obstacles = []
        
        # Zenoh session for sensor data
        logging.info("Initializing Zenoh session for navigation...")
        self.zenoh_conf = zenoh.Config()
        self.zenoh_session = None
        self.lidar_subscriber = None
        self.odom_subscriber = None
        
        # Control parameters
        self.path = []
        self.is_navigating = False
        self.navigation_start_time = 0
        self.target_reached = False
        
    async def initialize(self):
        """Initialize the navigation system"""
        try:
            self.zenoh_session = zenoh.open(self.zenoh_conf)
            
            # Subscribe to LIDAR data
            self.lidar_subscriber = self.zenoh_session.declare_subscriber(
                "*/scan", self._lidar_callback
            )
            
            # Subscribe to odometry data
            self.odom_subscriber = self.zenoh_session.declare_subscriber(
                "*/odom", self._odom_callback
            )
            
            logging.info("AdaptiveNav connector initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize AdaptiveNav connector: {e}")
    
    def _lidar_callback(self, sample):
        """Process LIDAR data to update obstacle map"""
        try:
            scan = sensor_msgs.LaserScan.deserialize(sample.payload.to_bytes())
            
            # Clear previous obstacles
            self.grid.clear_obstacles()
            
            # Process LIDAR data to identify obstacles
            angle = scan.angle_min
            for i, distance in enumerate(scan.ranges):
                if math.isfinite(distance) and distance > 0.1 and distance < 5.0:
                    # Convert polar to cartesian coordinates
                    obstacle_x = self.current_position.x + distance * math.cos(angle + self.current_orientation)
                    obstacle_y = self.current_position.y + distance * math.sin(angle + self.current_orientation)
                    
                    # Add to occupancy grid with appropriate size
                    self.grid.set_obstacle(obstacle_x, obstacle_y, radius=0.15)
                
                angle += scan.angle_increment
            
            # If we're navigating and dynamic replanning is enabled, check if we need to replan
            if self.is_navigating and self.args and self.args.enable_dynamic_replanning:
                self._check_path_validity()
        
        except Exception as e:
            logging.error(f"Error processing LIDAR data: {e}")
    
    def _odom_callback(self, sample):
        """Process odometry data to update robot position"""
        try:
            odom = sensor_msgs.Odometry.deserialize(sample.payload.to_bytes())
            
            # Update current position
            self.current_position.x = odom.pose.pose.position.x
            self.current_position.y = odom.pose.pose.position.y
            
            # Extract orientation (yaw) from quaternion
            q = odom.pose.pose.orientation
            self.current_orientation = math.atan2(
                2.0 * (q.w * q.z + q.x * q.y),
                1.0 - 2.0 * (q.y * q.y + q.z * q.z)
            )
            
            # Check if we've reached the target
            if self.is_navigating and self.args and self.args.target:
                self._check_target_reached()
        
        except Exception as e:
            logging.error(f"Error processing odometry data: {e}")
    
    def _check_path_validity(self):
        """Check if the current path is still valid or needs replanning"""
        if not self.path or not self.args or not self.args.target:
            return
            
        # Check if any obstacles are blocking the path
        for point in self.path:
            grid_x, grid_y = self.grid.world_to_grid(point.x, point.y)
            if self.grid.grid[(grid_x, grid_y)].occupied:
                logging.info("Path blocked by obstacle, replanning...")
                # Replan from current position
                self.path = self.planner.plan_path(
                    self.current_position, 
                    self.args.target,
                    social_mode=(self.args.mode == NavigationMode.SOCIAL)
                )
                self.path = self.planner.smooth_path(self.path)
                break
    
    def _check_target_reached(self):
        """Check if we've reached the target position"""
        if not self.args or not self.args.target:
            return
            
        # Calculate distance to target
        dx = self.args.target.x - self.current_position.x
        dy = self.args.target.y - self.current_position.y
        distance = math.sqrt(dx*dx + dy*dy)
        
        # If we're close enough to the target
        if distance < 0.2:  # 20cm threshold
            self.target_reached = True
            self.is_navigating = False
            logging.info(f"Target reached. Distance: {distance:.2f}m")
    
    def _calculate_path_length(self, path: List[Point2D]) -> float:
        """Calculate the total length of a path"""
        if not path or len(path) < 2:
            return 0.0
            
        length = 0.0
        for i in range(1, len(path)):
            dx = path[i].x - path[i-1].x
            dy = path[i].y - path[i-1].y
            length += math.sqrt(dx*dx + dy*dy)
            
        return length
    
    async def invoke(self, args: NavigationInput) -> NavigationOutput:
        """
        Start adaptive navigation to the target position.
        
        Parameters
        ----------
        args : NavigationInput
            Navigation parameters including target, mode, etc.
            
        Returns
        -------
        NavigationOutput
            Navigation result
        """
        self.args = args
        
        # Create output object
        output = NavigationOutput()
        
        # Validate input
        if not args.target:
            output.message = "No target position provided"
            return output
        
        # Initialize if not already done
        if not self.zenoh_session:
            await self.initialize()
        
        # Reset navigation state
        self.is_navigating = True
        self.target_reached = False
        self.navigation_start_time = time.time()
        
        # Plan initial path based on navigation mode
        social_mode = (args.mode == NavigationMode.SOCIAL)
        self.path = self.planner.plan_path(
            self.current_position, 
            args.target,
            social_mode=social_mode
        )
        
        # Smooth the path
        self.path = self.planner.smooth_path(self.path)
        
        if not self.path:
            output.message = "Failed to plan a path to the target"
            self.is_navigating = False
            return output
        
        # Calculate path statistics
        path_length = self._calculate_path_length(self.path)
        estimated_time = path_length / args.max_speed
        obstacles_detected = len(self.grid.obstacles)
        
        # Update output
        output.path_points = self.path
        output.path_length = path_length
        output.estimated_time = estimated_time
        output.obstacles_detected = obstacles_detected
        
        # Wait for navigation to complete (timeout or reached target)
        timeout_time = self.navigation_start_time + args.path_timeout
        
        while time.time() < timeout_time and not self.target_reached and self.is_navigating:
            await asyncio.sleep(0.1)
        
        # Check why we stopped
        if self.target_reached:
            output.success = True
            output.message = f"Successfully reached target. Path length: {path_length:.2f}m"
        elif time.time() >= timeout_time:
            output.success = False
            output.message = f"Navigation timed out after {args.path_timeout} seconds"
        else:
            output.success = False
            output.message = "Navigation stopped unexpectedly"
        
        self.is_navigating = False
        return output
    
    async def cleanup(self):
        """Clean up resources"""
        if self.zenoh_session:
            if self.lidar_subscriber:
                self.lidar_subscriber.undeclare()
            if self.odom_subscriber:
                self.odom_subscriber.undeclare()
            self.zenoh_session.close()
            self.zenoh_session = None 