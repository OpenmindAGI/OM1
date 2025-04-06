import numpy as np
import zenoh
from src.simulators.plugins.MapGeneratorPlugin import MapGeneratorPlugin
from src.zenoh_idl import sensor_msgs

class GazeboMappingAdapter:
    """
    Adapter class that connects Gazebo simulator with the mapping plugin.
    It handles communication with Gazebo via Zenoh and converts sensor data
    to the format expected by the MapGeneratorPlugin.
    """
    
    def __init__(self, config=None):
        # Initialize Zenoh session
        self.session = zenoh.open()
        
        # Subscribe to laser scan topic
        self.sub_scan = self.session.declare_subscriber(
            "URID/pi/scan",
            lambda sample: self._process_scan(sample)
        )
        
        # Subscribe to robot pose/odometry topic
        self.sub_odom = self.session.declare_subscriber(
            "odom",
            lambda sample: self._process_odom(sample)
        )
        
        # Initialize data storage
        self.latest_scan = None
        self.latest_pose = [0.0, 0.0, 0.0]  # x, y, theta
        
        # Create the mapping plugin
        self.map_generator = MapGeneratorPlugin(self, config)
    
    def _process_scan(self, sample):
        """Process incoming laser scan data"""
        try:
            scan = sensor_msgs.LaserScan.deserialize(sample.payload.to_bytes())
            self.latest_scan = {
                'ranges': scan.ranges,
                'angle_min': scan.angle_min,
                'angle_max': scan.angle_max,
                'angle_increment': scan.angle_increment,
                'range_min': scan.range_min,
                'range_max': scan.range_max
            }
        except Exception as e:
            print(f"Error processing laser scan: {e}")
    
    def _process_odom(self, sample):
        """Process incoming odometry data"""
        try:
            # The exact format of odometry data may vary; adjust as needed
            odom = sensor_msgs.Odometry.deserialize(sample.payload.to_bytes())
            
            position = odom.pose.pose.position
            orientation = odom.pose.pose.orientation
            
            # Extract position
            x = position.x
            y = position.y
            
            # Extract orientation (convert quaternion to euler angle)
            # This is a simplified conversion - only extracting yaw
            qx, qy, qz, qw = orientation.x, orientation.y, orientation.z, orientation.w
            yaw = np.arctan2(2.0 * (qw * qz + qx * qy), 
                            1.0 - 2.0 * (qy * qy + qz * qz))
            
            self.latest_pose = [x, y, yaw]
        except Exception as e:
            print(f"Error processing odometry: {e}")
    
    def get_robot_pose(self):
        """Return the latest robot pose for the mapping plugin"""
        return self.latest_pose
    
    def get_laser_scan(self):
        """Return the latest laser scan for the mapping plugin"""
        return self.latest_scan
    
    def start(self):
        """Start the mapping process"""
        self.map_generator.start()
        print("Gazebo mapping adapter started.")
    
    def stop(self):
        """Stop the mapping process and clean up resources"""
        self.map_generator.stop()
        
        # Clean up Zenoh subscriptions
        self.session.undeclare_subscriber(self.sub_scan)
        self.session.undeclare_subscriber(self.sub_odom)
        self.session.close()
        
        print("Gazebo mapping adapter stopped. Final map saved.") 