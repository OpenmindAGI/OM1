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

# Global variable for the adapter to access in signal handler
adapter = None

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
    
    try:
        print("Starting Gazebo mapping example...")
        
        # Create the adapter and start mapping
        adapter = GazeboMappingAdapter(config)
        adapter.start()
        
        print(f"Mapping started. Maps will be saved to the 'maps' directory.")
        print("Press Ctrl+C to stop mapping and save the final map.")
        
        # Run for a specified duration or indefinitely
        if args.duration > 0:
            print(f"Mapping will run for {args.duration} seconds.")
            time.sleep(args.duration)
            adapter.stop()
            print(f"Mapping completed after {args.duration} seconds.")
        else:
            # Run indefinitely until Ctrl+C
            print("Mapping will run until Ctrl+C is pressed.")
            while True:
                time.sleep(1)
                
    except Exception as e:
        print(f"Error in mapping example: {e}")
        if adapter:
            adapter.stop()
        sys.exit(1) 