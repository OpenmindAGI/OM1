# Gazebo_simulation
Repo for quadruped simulation and control with OM1.

# Dependencies
ROS2 is required for the simulation to interact with OM1, check https://docs.ros.org/en/humble/Installation.html for installation instructions.
ffmpeg is required for streaming the simulated video feed to OM1. If your system doesn't have `ffmpeg`, you should install it to run the program.
* To install on Mac, use `brew install ffmpeg`
* On Linux, use `sudo apt-get install ffmpeg`

# Run simulation locally
To start the simulation, do the following:
```
cd simulation
bash start_simulation.sh
```
After building, this should spin up a Gazebo window and a terminal for manual control of the robot. Wait until the line 'Simulation is running.'. 

To exit, do the following:
```
bash stop.sh
```
This is to avoid having background processes left running. 

Boot OM1 using the example config, remember to set the correct API key
```
uv run src/run.py quadruped_sim
```
_Note:_ The simulated camera feed is streamed to a virtual video device at `/dev/video10`, thus requiring the `camera_index` in the VLM config to be 10. Modify as needed if the virtual camera needs to be reordered or if OM1 needs to read from another camera.
