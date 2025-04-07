import logging
import asyncio
from typing import Optional

from actions.adaptive_nav.connector.navigator import AdaptiveNavConnector
from actions.adaptive_nav.connector.movement_controller import MovementController
from actions.adaptive_nav.interface import (
    AdaptiveNav, 
    NavigationInput, 
    NavigationOutput
)
from actions.base import ActionConnector


class AdaptiveNavRos2Connector(ActionConnector[NavigationOutput]):
    """
    ROS2 implementation of adaptive navigation for robots like TurtleBot4.
    
    This connector integrates our adaptive navigation system with ROS2-based
    robots, providing real-time path planning and obstacle avoidance.
    """
    def __init__(self):
        super().__init__()
        self.navigator = AdaptiveNavConnector()
        self.movement_controller = MovementController()
        self._initialized = False
        
    async def initialize(self):
        """Initialize the navigation system and movement controller"""
        if self._initialized:
            return
        
        await self.navigator.initialize()
        await self.movement_controller.initialize()
        self._initialized = True
        logging.info("AdaptiveNavRos2Connector initialized")
    
    async def invoke(self, args: NavigationInput) -> NavigationOutput:
        """
        Execute adaptive navigation using ROS2.
        
        Parameters
        ----------
        args : NavigationInput
            Navigation parameters including target position, mode, etc.
            
        Returns
        -------
        NavigationOutput
            The result of the navigation attempt
        """
        try:
            # Ensure initialization
            if not self._initialized:
                await self.initialize()
            
            # Configure movement controller based on navigation mode
            self.movement_controller.set_navigation_mode(args.mode)
            
            # Generate path plan using navigator
            nav_result = await self.navigator.invoke(args)
            
            # If path planning failed, return immediately
            if not nav_result.success or not nav_result.path_points:
                logging.warning(f"Path planning failed: {nav_result.message}")
                return nav_result
            
            # Set the path in the movement controller
            self.movement_controller.set_path(nav_result.path_points)
            
            # Execute the path
            execution_task = asyncio.create_task(
                self.movement_controller.execute_path(
                    self.navigator.current_position,
                    self.navigator.current_orientation
                )
            )
            
            # Wait for path execution to complete
            execution_success = await execution_task
            
            if execution_success:
                nav_result.success = True
                nav_result.message = "Navigation completed successfully"
            else:
                nav_result.success = False
                nav_result.message = "Path execution failed"
            
            return nav_result
            
        except Exception as e:
            logging.error(f"Error in AdaptiveNavRos2Connector: {e}")
            # Ensure robot stops in case of error
            self.movement_controller.stop()
            
            # Return error result
            output = NavigationOutput()
            output.success = False
            output.message = f"Navigation error: {str(e)}"
            return output
    
    async def cleanup(self):
        """Clean up resources used by the connector"""
        try:
            # Stop any ongoing movement
            self.movement_controller.stop()
            
            # Clean up movement controller
            self.movement_controller.cleanup()
            
            # Clean up navigator
            await self.navigator.cleanup()
            
            self._initialized = False
            logging.info("AdaptiveNavRos2Connector cleaned up")
        except Exception as e:
            logging.error(f"Error cleaning up AdaptiveNavRos2Connector: {e}")


def get_connector() -> ActionConnector:
    """
    Factory function to create a new connector instance.
    
    Returns
    -------
    ActionConnector
        A new instance of the AdaptiveNavRos2Connector
    """
    return AdaptiveNavRos2Connector() 