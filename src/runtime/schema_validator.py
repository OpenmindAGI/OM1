"""
Schema validator for configuration files.

This module provides functions to validate configuration files against a schema.
"""

import json5
import logging
import os
import sys
from typing import Dict, Any, Optional, List

# Try to import jsonschema
try:
    import jsonschema
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    logging.warning(
        "jsonschema module not found. Validation will be disabled.\n"
        "Please install it using one of these commands:\n"
        "  uv pip install jsonschema\n"
        "  pip install jsonschema\n"
        "  python -m pip install jsonschema"
    )

# Define the schema for configuration files
CONFIG_SCHEMA = {
    "type": "object",
    "required": ["hertz", "name", "system_prompt_base", "system_governance", 
                "system_prompt_examples", "agent_inputs", "cortex_llm", "agent_actions"],
    "properties": {
        "hertz": {
            "type": "number",
            "minimum": 0
        },
        "name": {
            "type": "string"
        },
        "api_key": {
            "type": ["string", "null"]
        },
        "URID": {
            "type": ["string", "null"]
        },
        "unitree_ethernet": {
            "type": ["string", "null"]
        },
        "system_prompt_base": {
            "type": "string"
        },
        "system_governance": {
            "type": "string"
        },
        "system_prompt_examples": {
            "type": "string"
        },
        "agent_inputs": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type"],
                "properties": {
                    "type": {"type": "string"},
                    "config": {"type": "object"}
                }
            }
        },
        "cortex_llm": {
            "type": "object",
            "required": ["type"],
            "properties": {
                "type": {"type": "string"},
                "config": {"type": "object"}
            }
        },
        "simulators": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type"],
                "properties": {
                    "type": {"type": "string"},
                    "config": {"type": "object"}
                }
            }
        },
        "agent_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "implementation", "connector"],
                "properties": {
                    "name": {"type": "string"},
                    "llm_label": {"type": "string"},
                    "implementation": {"type": "string"},
                    "connector": {"type": "string"},
                    "config": {"type": "object"}
                }
            }
        }
    }
}

def validate_config(config_data: Dict[str, Any]) -> List[str]:
    """
    Validate a configuration against the schema.
    
    Parameters
    ----------
    config_data : Dict[str, Any]
        The configuration data to validate
        
    Returns
    -------
    List[str]
        List of validation errors, empty if validation is successful
    """
    if not JSONSCHEMA_AVAILABLE:
        return ["jsonschema module not available, validation skipped"]
    
    validator = jsonschema.Draft7Validator(CONFIG_SCHEMA)
    errors = list(validator.iter_errors(config_data))
    return [f"{error.path}: {error.message}" for error in errors]

def validate_config_file(config_path: str) -> List[str]:
    """
    Validate a configuration file against the schema.
    
    Parameters
    ----------
    config_path : str
        Path to the configuration file
        
    Returns
    -------
    List[str]
        List of validation errors, empty if validation is successful
        
    Raises
    ------
    FileNotFoundError
        If the configuration file does not exist
    json5.JSONDecodeError
        If the configuration file contains invalid JSON
    """
    if not JSONSCHEMA_AVAILABLE:
        return ["jsonschema module not available, validation skipped"]
    
    try:
        with open(config_path, "r") as f:
            config_data = json5.load(f)
        return validate_config(config_data)
    except json5.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in configuration file: {e}")
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

def validate_all_configs() -> Dict[str, List[str]]:
    """
    Validate all configuration files in the config directory.
    
    Returns
    -------
    Dict[str, List[str]]
        Dictionary mapping configuration file names to lists of validation errors
    """
    if not JSONSCHEMA_AVAILABLE:
        return {"all_configs": ["jsonschema module not available, validation skipped"]}
    
    config_folder_path = os.path.join(os.path.dirname(__file__), "../../config")
    file_names = [
        entry.name for entry in os.scandir(config_folder_path) if entry.is_file()
    ]
    
    results = {}
    for file_name in file_names:
        if not file_name.endswith(".json5"):
            continue
            
        config_path = os.path.join(config_folder_path, file_name)
        try:
            errors = validate_config_file(config_path)
            results[file_name] = errors
        except Exception as e:
            results[file_name] = [str(e)]
    
    return results 