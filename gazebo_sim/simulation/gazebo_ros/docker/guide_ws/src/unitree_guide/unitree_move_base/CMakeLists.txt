cmake_minimum_required(VERSION 2.8.3)
project(unitree_move_base)

find_package(catkin REQUIRED COMPONENTS
  geometry_msgs
  move_base_msgs
  roscpp
  rospy
  tf
  visualization_msgs
)

catkin_package()

include_directories(
  ${catkin_INCLUDE_DIRS}
)
