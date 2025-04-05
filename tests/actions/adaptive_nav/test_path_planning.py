import unittest
import math
from actions.adaptive_nav.interface import Point2D
from actions.adaptive_nav.connector.navigator import OccupancyGrid, AdaptivePathPlanner


class TestPathPlanning(unittest.TestCase):
    """Test the path planning capabilities of the adaptive navigation system"""

    def setUp(self):
        """Set up test fixtures"""
        self.grid = OccupancyGrid(width=20, height=20, resolution=0.1)
        self.planner = AdaptivePathPlanner(self.grid)

    def test_empty_grid_path(self):
        """Test path planning in an empty grid"""
        # Start and goal positions
        start = Point2D(x=-0.5, y=-0.5)
        goal = Point2D(x=0.5, y=0.5)

        # Plan path
        path = self.planner.plan_path(start, goal)

        # Check that path exists
        self.assertGreater(len(path), 0, "Should find a path in an empty grid")

        # Check that path starts and ends at the correct positions
        self.assertAlmostEqual(path[0].x, start.x, places=1)
        self.assertAlmostEqual(path[0].y, start.y, places=1)
        self.assertAlmostEqual(path[-1].x, goal.x, places=1)
        self.assertAlmostEqual(path[-1].y, goal.y, places=1)

    def test_obstacle_avoidance(self):
        """Test path planning with obstacles"""
        # Start and goal positions
        start = Point2D(x=-0.5, y=-0.5)
        goal = Point2D(x=0.5, y=0.5)

        # Add obstacle in the direct path
        self.grid.set_obstacle(0.0, 0.0, radius=0.2)

        # Plan path
        path = self.planner.plan_path(start, goal)

        # Check that path exists
        self.assertGreater(len(path), 0, "Should find a path around obstacle")

        # Check that path doesn't go through obstacle
        for point in path:
            distance = math.sqrt(point.x**2 + point.y**2)
            self.assertGreater(distance, 0.15, "Path should avoid obstacle")

    def test_no_path_possible(self):
        """Test when no path is possible"""
        # Start and goal positions
        start = Point2D(x=-0.5, y=-0.5)
        goal = Point2D(x=0.5, y=0.5)

        # Create a wall of obstacles blocking the path
        for y in range(-10, 10):
            self.grid.set_obstacle(0.0, y * 0.1, radius=0.1)

        # Plan path
        path = self.planner.plan_path(start, goal)

        # Check that no path was found
        self.assertEqual(len(path), 0, "Should not find a path through wall of obstacles")

    def test_path_smoothing(self):
        """Test path smoothing"""
        # Create a jagged path
        jagged_path = [
            Point2D(x=0.0, y=0.0),
            Point2D(x=0.2, y=0.0),
            Point2D(x=0.2, y=0.2),
            Point2D(x=0.4, y=0.2),
            Point2D(x=0.4, y=0.4),
            Point2D(x=0.6, y=0.4),
            Point2D(x=0.6, y=0.6),
        ]

        # Smooth the path
        smoothed_path = self.planner.smooth_path(jagged_path)

        # Check that the path is smoother (less sharp corners)
        self.assertEqual(len(smoothed_path), len(jagged_path), 
                        "Smoothed path should have same number of points")

        # Check that first and last points remain the same
        self.assertEqual(smoothed_path[0], jagged_path[0], 
                        "First point should remain the same")
        self.assertEqual(smoothed_path[-1], jagged_path[-1], 
                        "Last point should remain the same")

        # Check that internal points have changed (been smoothed)
        changed = False
        for i in range(1, len(jagged_path) - 1):
            if smoothed_path[i].x != jagged_path[i].x or smoothed_path[i].y != jagged_path[i].y:
                changed = True
                break
        self.assertTrue(changed, "Internal points should be smoothed")

    def test_social_mode_path_planning(self):
        """Test path planning in social mode with obstacles"""
        # Start and goal positions
        start = Point2D(x=-0.5, y=-0.5)
        goal = Point2D(x=0.5, y=0.5)

        # Add obstacle representing a human
        self.grid.set_obstacle(0.0, 0.0, radius=0.2)

        # Plan normal path
        normal_path = self.planner.plan_path(start, goal, social_mode=False)

        # Plan social path
        social_path = self.planner.plan_path(start, goal, social_mode=True)

        # Both paths should exist
        self.assertGreater(len(normal_path), 0, "Should find a normal path")
        self.assertGreater(len(social_path), 0, "Should find a social path")

        # Calculate minimum distance to obstacle for both paths
        normal_min_distance = float('inf')
        social_min_distance = float('inf')

        for point in normal_path:
            distance = math.sqrt(point.x**2 + point.y**2)
            normal_min_distance = min(normal_min_distance, distance)

        for point in social_path:
            distance = math.sqrt(point.x**2 + point.y**2)
            social_min_distance = min(social_min_distance, distance)

        # Social path should maintain more distance
        self.assertGreaterEqual(social_min_distance, normal_min_distance, 
                              "Social path should maintain more distance to obstacles")


if __name__ == '__main__':
    unittest.main() 