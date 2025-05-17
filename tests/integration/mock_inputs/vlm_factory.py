import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

from inputs.base import Sensor, SensorConfig
from tests.integration.mock_inputs.mock_image_provider import load_test_images
from tests.integration.mock_inputs.mock_vlm_coco import MockVLM_COCO

# Registry of mock VLM creators
MOCK_VLM_REGISTRY = {
    "MockVLM_COCO": lambda config: MockVLM_COCO(config),
    # Also register with the original names for direct usage
    "VLM_COCO_Local": lambda config: MockVLM_COCO(config),
}


def create_mock_vlm(vlm_type: str, vlm_config: Dict[str, Any]) -> Optional[Sensor]:
    """
    Create a mock VLM of the specified type.

    Parameters
    ----------
    vlm_type : str
        Type of the VLM to create
    vlm_config : Dict[str, Any]
        Configuration for the VLM

    Returns
    -------
    Optional[Sensor]
        Created mock VLM or None if type is not supported
    """
    if vlm_type not in MOCK_VLM_REGISTRY:
        logging.error(f"Unsupported VLM type: {vlm_type}")
        return None

    try:
        # Convert the dict config to SensorConfig
        sensor_config = SensorConfig(**vlm_config)

        # Create the mock VLM
        mock_vlm = MOCK_VLM_REGISTRY[vlm_type](sensor_config)
        logging.info(f"Created mock VLM of type {vlm_type}")
        return mock_vlm
    except Exception as e:
        logging.error(f"Error creating mock VLM of type {vlm_type}: {e}")
        return None


def load_test_config(config_path: str) -> Dict[str, Any]:
    """
    Load a test configuration from a file.

    Parameters
    ----------
    config_path : str
        Path to the test configuration file

    Returns
    -------
    Dict[str, Any]
        Loaded test configuration
    """
    # Implementation depends on your configuration file format
    # This is a placeholder
    with open(config_path, "r") as f:
        return json.load(f)


def setup_vlm_from_config(
    config_path: Path,
    test_images: List[Image.Image],
    image_metadata: Dict[str, Any] = None,
) -> Optional[Sensor]:
    """
    Set up a mock VLM based on configuration and test images.

    Parameters
    ----------
    config_path : Path
        Path to the test configuration file
    test_images : List[Image.Image]
        List of test images to use
    image_metadata : Dict[str, Any], optional
        Metadata to associate with the test images

    Returns
    -------
    Optional[Sensor]
        Configured mock VLM or None if configuration is invalid
    """
    # Load the configuration
    config = load_test_config(config_path)
    if not config:
        return None

    # Initialize the image provider with test images
    load_test_images(test_images, image_metadata)

    # Find the VLM configuration
    vlm_config = None
    vlm_type = None

    # Look for VLM in agent_inputs
    if "agent_inputs" in config:
        for input_config in config["agent_inputs"]:
            if input_config.get("type") in ("VLM_COCO_Local", "VLMGemini"):
                vlm_type = input_config.get("type")
                vlm_config = input_config.get("config", {})
                break

    if not vlm_type:
        # If not found in agent_inputs, check if there's a test_vlm section
        if "test_vlm" in config:
            vlm_type = config["test_vlm"].get("type")
            vlm_config = config["test_vlm"].get("config", {})

    if not vlm_type:
        logging.error("No VLM configuration found in config file")
        return None

    # Create the mock VLM
    return create_mock_vlm(vlm_type, vlm_config)
