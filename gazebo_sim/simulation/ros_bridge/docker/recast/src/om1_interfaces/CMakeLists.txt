cmake_minimum_required(VERSION 3.5)
project(om1_interfaces)

# Default to C99
if(NOT CMAKE_C_STANDARD)
  set(CMAKE_C_STANDARD 99)
endif()

# Default to C++14
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 14)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(rosidl_generator_dds_idl REQUIRED)

# uncomment the following section in order to fill in
# further dependencies manually.

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/Cmd.msg"
  "msg/State.msg"
  "msg/Move.msg"
  "msg/RpyCmd.msg"
  "msg/IMU.msg"
  "msg/AI.msg"
  "msg/ETH.msg"
  "msg/TELESTAT.msg"
  "msg/RangeInfo.msg"

  DEPENDENCIES geometry_msgs
)

rosidl_generate_dds_interfaces(
  ${rosidl_generate_interfaces_TARGET}__dds_connext_idl
  IDL_TUPLES ${rosidl_generate_interfaces_IDL_TUPLES}
  OUTPUT_SUBFOLDERS "dds_connext"
)
add_dependencies(
  ${PROJECT_NAME}
  ${PROJECT_NAME}__dds_connext_idl
)

ament_package()
