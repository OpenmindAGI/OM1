cmake_minimum_required(VERSION 3.0.2)
project(om1_msgs)

# Default to C++14
set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find dependencies
find_package(catkin REQUIRED COMPONENTS
  message_generation
  geometry_msgs
  std_msgs
)

# Declare ROS messages
add_message_files(
  DIRECTORY msg
  FILES
  Cmd.msg
  State.msg
  Move.msg
  RpyCmd.msg
  IMU.msg
  AI.msg
  ETH.msg
  TELESTAT.msg
  RangeInfo.msg
)

# Generate added messages and services
generate_messages(
  DEPENDENCIES
  geometry_msgs
  std_msgs
)

# Declare a catkin package
catkin_package(
  CATKIN_DEPENDS
  message_runtime
  geometry_msgs
  std_msgs
)

# Include directories
include_directories(
  ${catkin_INCLUDE_DIRS}
)
