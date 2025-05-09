"""
Mock input registry for integration tests.

This module allows mock input plugins to be registered temporarily with the
main input loading system during tests.
"""

import logging
import sys

from tests.integration.mock_inputs.mock_vlm_coco import MockVLM_COCO

# Store original classes to restore them later
_original_classes = {}


def register_mock_inputs():
    """
    Register mock inputs by directly replacing the classes in the inputs module.

    This approach is more direct and reliable than patching the load_input function.
    """
    # Import all the modules we need to modify
    import inputs.plugins.vlm_coco_local

    # Save original classes for later restoration
    global _original_classes
    _original_classes = {"VLM_COCO_Local": inputs.plugins.vlm_coco_local.VLM_COCO_Local}

    # Replace with mock classes
    inputs.plugins.vlm_coco_local.VLM_COCO_Local = MockVLM_COCO

    # Also add our mocks to the module namespace so they're discoverable
    sys.modules["inputs.plugins.mock_vlm_coco"] = type(
        "MockModule", (), {"MockVLM_COCO": MockVLM_COCO}
    )

    logging.info("Registered mock inputs by directly replacing classes")


def unregister_mock_inputs():
    """
    Restore the original input classes.
    """
    global _original_classes

    if _original_classes:
        # Restore original classes
        import inputs.plugins.vlm_coco_local

        inputs.plugins.vlm_coco_local.VLM_COCO_Local = _original_classes.get(
            "VLM_COCO_Local"
        )

        # Remove mock modules
        if "inputs.plugins.mock_vlm_coco" in sys.modules:
            del sys.modules["inputs.plugins.mock_vlm_coco"]

        _original_classes = {}
        logging.info("Unregistered mock inputs and restored original classes")
