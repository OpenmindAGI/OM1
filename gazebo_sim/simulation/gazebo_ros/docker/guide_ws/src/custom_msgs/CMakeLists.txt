cmake_minimum_required(VERSION 3.0.2)
project(custom_msgs)

# Find required packages
find_package(catkin REQUIRED COMPONENTS
  message_generation
  std_msgs
  geometry_msgs
)

# Add message files
add_message_files(
  FILES
  Vector4.msg
  UserInput.msg
)

# Generate message files
generate_messages(
  DEPENDENCIES
  std_msgs
  geometry_msgs
)

# Declare this package as a catkin package
catkin_package(
  CATKIN_DEPENDS message_runtime std_msgs geometry_msgs
)
