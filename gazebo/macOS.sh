#!/usr/bin/env bash

# ------------------------------------------------------------------
# Script: run_gazebo.sh
#
# Description:
#   - Checks if the platform is macOS. If not, prints a warning.
#   - Checks if Gazebo Harmonic (gz) is installed.
#   - If not, asks the user whether to install it via Homebrew.
#   - Exports GZ_SIM_RESOURCE_PATH to the folder where this script is located.
#   - Runs gz sim with a specified model file in the current terminal.
#   - Opens a new Terminal window to run gz sim -g.
#
# ------------------------------------------------------------------

# Check if the platform is macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo "Warning: This script is designed for macOS. You are running on $(uname)."
    echo "The new Terminal window may not open as expected."
fi

# Check if gz (Gazebo Harmonic) is installed.
if ! command -v gz sim &> /dev/null; then
    echo "gz (Gazebo Harmonic) is not installed."
    read -p "Would you like to install Gazebo Harmonic using Homebrew? (y/n): " install_choice
    if [[ "$install_choice" =~ ^[Yy]$ ]]; then
        echo "Tapping osrf/simulation..."
        brew tap osrf/simulation
        echo "Installing gz-harmonic..."
        brew install gz-harmonic
        if [ $? -ne 0 ]; then
            echo "Installation failed. Please check your Homebrew setup."
            exit 1
        fi
    else
        echo "gz is required. Exiting."
        exit 1
    fi
fi

# Get the directory where the script is located.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export GZ_SIM_RESOURCE_PATH="$SCRIPT_DIR"
echo "GZ_SIM_RESOURCE_PATH set to: $GZ_SIM_RESOURCE_PATH"

# Get the model file name from the first argument, default to model.sdf
FILE_NAME="${1:-model.sdf}"

# Define the model file path relative to the script directory.
MODEL_FILE="$SCRIPT_DIR/gz/models/$FILE_NAME"
if [ ! -f "$MODEL_FILE" ]; then
    echo "Error: Model file not found at $MODEL_FILE"
    exit 1
fi

# Run gz sim with the specified model in simulation mode (-s) in the current terminal.
echo "Starting Gazebo simulation with model: $MODEL_FILE"
gz sim "$MODEL_FILE" -s &

# Open a new Terminal window to run gz sim in GUI mode (-g).
echo "Opening a new Terminal window for gz sim -g..."
osascript <<EOF
tell application "Terminal"
    do script "export GZ_SIM_RESOURCE_PATH='$SCRIPT_DIR'; gz sim -g &"
end tell
EOF

# End of script
