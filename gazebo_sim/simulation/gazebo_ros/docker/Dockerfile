# Use the official ROS Noetic full desktop image
FROM ros:noetic-ros-base-focal

# Set environment variables for ROS and DEBIAN frontend
ENV ROS_DISTRO=noetic \
    DEBIAN_FRONTEND=noninteractive

# install bootstrap tools
RUN apt-get update && apt-get install --no-install-recommends -y \
    build-essential \
    python3-rosdep \
    python3-rosinstall \
    python3-vcstools \
    && rm -rf /var/lib/apt/lists/*

# install ros packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-noetic-desktop-full=1.5.0-1* \
    && rm -rf /var/lib/apt/lists/*

# Update and install required packages, including Gazebo 11.14.0
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        wget \
        lsb-release \
        gnupg2 \
        curl

#     echo "deb http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" > /etc/apt/sources.list.d/gazebo-stable.list && \
#     wget https://packages.osrfoundation.org/gazebo.key -O - | apt-key add - && \
#     apt-get update && \
#     apt-get install -y --no-install-recommends \
#         gazebo11=11.14.0-1* \
#         ros-${ROS_DISTRO}-gazebo-ros-pkgs \
#         ros-${ROS_DISTRO}-gazebo-ros-control && \
#     rm -rf /var/lib/apt/lists/*

# Install additional useful ROS packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ros-${ROS_DISTRO}-gazebo-ros-pkgs \
        ros-${ROS_DISTRO}-gazebo-ros-control \
        ros-${ROS_DISTRO}-joint-state-controller \
        ros-${ROS_DISTRO}-robot-state-publisher \
        ros-${ROS_DISTRO}-xacro \
        ros-${ROS_DISTRO}-move-base-msgs \
        liblcm-dev && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace

# COPY ./start.sh /app/start.sh
COPY ./guide_ws /app/guide_ws

RUN /bin/bash -c "source /opt/ros/noetic/setup.bash && cd /app/guide_ws && catkin_make"

RUN echo "source /opt/ros/noetic/setup.bash" >> /root/.bashrc && \
    echo "source /app/guide_ws/devel/setup.bash" >> /root/.bashrc

COPY ./stream /workspace/stream

# Set the default command
CMD ["/bin/bash"]