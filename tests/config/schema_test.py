import json
import json5
import os
import jsonschema
from typing import Dict, Any, List, Optional, Union, Tuple
from pathlib import Path


OM1_API_KEY = "openmind_free"

# Load the schema for validating the configuration files from config-schema.json
SCHEMA_FILE_PATH = Path(__file__).parent.parent.parent / "config" / "config-schema.json"
BASE_RESPONSE_SCHEMA_FILE_PATH = Path(__file__).parent.parent.parent / "config" / "base-response-schema.json"

def load_schema(schema_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Load a JSON schema from a file.
    
    Args:
        schema_path: Path to the schema file
        
    Returns:
        Dict containing the loaded schema
    """
    schema_path = Path(schema_path)
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    
    with open(schema_path, 'r', encoding='utf-8') as f:
        return json.load(f)

try:
    CONFIG_SCHEMA = load_schema(SCHEMA_FILE_PATH)
except Exception as e:
    raise RuntimeError(f"Failed to load configuration schema: {e}")

try:
    BASE_RESPONSE_SCHEMA = load_schema(BASE_RESPONSE_SCHEMA_FILE_PATH)
except Exception as e:
    raise RuntimeError(f"Failed to load base response schema: {e}")

def load_config(config_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Load a JSON5 configuration file.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        Dict containing the loaded configuration
    """
    config_path = Path(config_path)
    
    print(f"DEBUG: Attempting to load config file: {config_path} (exists: {config_path.exists()})")
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            if config_path.suffix.lower() == '.json5':
                print(f"DEBUG: Loading as JSON5: {config_path}")
                config = json5.load(f)
            else:
                print(f"DEBUG: Loading as regular JSON: {config_path}")
                config = json.load(f)
        print(f"DEBUG: Successfully loaded: {config_path}")
        return config
    except Exception as e:
        print(f"DEBUG: Error loading {config_path}: {str(e)}")
        raise ValueError(f"Failed to load configuration file {config_path}: {str(e)}")

def validate_config(config: Dict[str, Any]) -> List[str]:
    """
    Validate a configuration against the schema.
    
    Args:
        config: Configuration dict to validate
        
    Returns:
        List of validation errors (empty if valid)
    """
    try:
        print(f"DEBUG: Validating config with keys: {', '.join(config.keys())}")
        jsonschema.validate(instance=config, schema=CONFIG_SCHEMA)
        print("DEBUG: Validation successful")
        return []
    except jsonschema.exceptions.ValidationError as e:
        # Return detailed error information
        path = ".".join(str(p) for p in e.path)
        error_msg = f"Validation error at {path}: {e.message}"
        print(f"DEBUG: {error_msg}")
        return [error_msg]

def validate_config_file(config_path: Union[str, Path]) -> List[str]:
    """
    Load and validate a configuration file.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        List of validation errors (empty if valid)
    """
    print(f"DEBUG: Validating file: {config_path}")
    try:
        config = load_config(config_path)
        return validate_config(config)
    except Exception as e:
        error_msg = str(e)
        print(f"DEBUG: Error in validate_config_file: {error_msg}")
        return [error_msg]

def validate_all_configs(config_dir: Union[str, Path] = None) -> Dict[str, List[str]]:
    """
    Validate all configuration files in a directory.
    
    Args:
        config_dir: Directory containing configuration files (defaults to current directory)
        
    Returns:
        Dict mapping configuration file names to lists of validation errors
    """
    # Use current directory if none specified
    if config_dir is None:
        config_dir = Path.cwd()
    else:
        config_dir = Path(config_dir)
        
    results = {}
    
    print(f"DEBUG: Looking for config files in: {config_dir.absolute()}")
    print(f"DEBUG: Current working directory: {Path.cwd().absolute()}")
    
    # Debug - list all files in the directory
    if config_dir.exists():
        print("DEBUG: Directory contents:")
        for item in config_dir.iterdir():
            print(f"  - {item.name} ({'dir' if item.is_dir() else 'file'})")
    else:
        print(f"DEBUG: Directory {config_dir} does not exist!")
    
    json5_files = list(config_dir.glob("*.json5"))
    print(f"DEBUG: Found {len(json5_files)} JSON5 files")
    
    for file_path in json5_files:
        if file_path.name == "keys.json5":
            print(f"DEBUG: Skipping {file_path.name}")
            continue
        
        print(f"DEBUG: Processing config file: {file_path.name}")
        errors = validate_config_file(file_path)
        results[file_path.name] = errors
    
    return results

def print_validation_results(results: Dict[str, List[str]]):
    """
    Print validation results in a human-readable format.
    
    Args:
        results: Dict mapping configuration file names to lists of validation errors
    """
    valid_count = sum(1 for errors in results.values() if not errors)
    total_count = len(results)
    
    print(f"\nValidation results: {valid_count}/{total_count} files are valid")
    print("=" * 60)
    
    for filename, errors in sorted(results.items()):
        if errors:
            print(f"\n❌ {filename} - {len(errors)} error(s):")
            for i, error in enumerate(errors, 1):
                print(f"  {i}. {error}")
        else:
            print(f"✅ {filename} - Valid")
    
    print("\n")

def get_config_response_schema(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a JSON schema for validating agent responses based on the config.
    
    Args:
        config: The agent configuration
        
    Returns:
        JSON schema for validating responses
    """
    # Create a copy of the base response schema
    response_schema = {
        "$schema": BASE_RESPONSE_SCHEMA["$schema"],
        "type": BASE_RESPONSE_SCHEMA["type"],
        "properties": dict(BASE_RESPONSE_SCHEMA["properties"])
    }
    
    # Extract valid actions from the config
    valid_properties = {}
    required_properties = []
    
    for action in config.get("agent_actions", []):
        action_name = action.get("llm_label") or action.get("name")
        if action_name and action_name in response_schema["properties"]:
            valid_properties[action_name] = response_schema["properties"][action_name]
    
    # If no matching properties were found, fall back to the base schema
    if not valid_properties:
        valid_properties = response_schema["properties"]
    
    # Set the valid properties and additional properties rule
    response_schema["properties"] = valid_properties
    response_schema["additionalProperties"] = False
    
    return response_schema

def validate_agent_response(config: Dict[str, Any], response: Dict[str, Any]) -> List[str]:
    """
    Validate an agent response against the expected schema.
    
    Args:
        config: The agent configuration
        response: The agent response to validate
        
    Returns:
        List of validation errors (empty if valid)
    """
    response_schema = get_config_response_schema(config)
    
    try:
        jsonschema.validate(instance=response, schema=response_schema)
        return []
    except jsonschema.exceptions.ValidationError as e:
        path = ".".join(str(p) for p in e.path)
        return [f"Response validation error at {path}: {e.message}"]

def update_api_key_in_config(config_path: Union[str, Path], api_key: str = None) -> Tuple[bool, str]:
    """
    Update the API key in a configuration file.
    
    Args:
        config_path: Path to the configuration file
        api_key: API key to use (defaults to OM1_API_KEY from keys.py)
        
    Returns:
        Tuple of (success, message)
    """
    if api_key is None:
        api_key = OM1_API_KEY
    
    if api_key is None:
        return False, "API key not provided and not found in keys.py"
    
    try:
        config = load_config(config_path)
        config["api_key"] = api_key
        
        with open(config_path, 'w', encoding='utf-8') as f:
            if Path(config_path).suffix.lower() == '.json5':
                json5.dump(config, f, indent=2)
            else:
                json.dump(config, f, indent=2)
        
        return True, f"Successfully updated API key in {config_path}"
    except Exception as e:
        return False, f"Failed to update API key in {config_path}: {str(e)}"

def update_all_api_keys(config_dir: Union[str, Path] = None, api_key: str = None) -> Dict[str, str]:
    """
    Update API keys in all configuration files in a directory.
    
    Args:
        config_dir: Directory containing configuration files (defaults to current directory)
        api_key: API key to use (defaults to OM1_API_KEY from keys.py)
        
    Returns:
        Dict mapping configuration file names to update results
    """
    # Use current directory if none specified
    if config_dir is None:
        config_dir = Path.cwd()
    else:
        config_dir = Path(config_dir)
        
    results = {}
    
    print(f"DEBUG: Updating API keys in directory: {config_dir.absolute()}")
    json5_files = list(config_dir.glob("*.json5"))
    print(f"DEBUG: Found {len(json5_files)} JSON5 files for API key update")
    
    for file_path in json5_files:
        if file_path.name == "keys.json5":
            continue
        
        print(f"DEBUG: Updating API key in: {file_path.name}")
        success, message = update_api_key_in_config(file_path, api_key)
        results[file_path.name] = message
    
    return results

def load_and_validate_config(config_name: str, config_dir: Union[str, Path] = None) -> Dict[str, Any]:
    """
    Load and validate a named configuration file.
    
    Args:
        config_name: Name of the configuration file (with or without extension)
        config_dir: Directory containing configuration files (defaults to current directory)
        
    Returns:
        The loaded configuration if valid
        
    Raises:
        ValueError: If the configuration is not valid
        FileNotFoundError: If the configuration file is not found
    """
    # Use current directory if none specified
    if config_dir is None:
        config_dir = Path.cwd()
    else:
        config_dir = Path(config_dir)
    
    # Ensure .json5 extension
    if not config_name.endswith('.json5'):
        config_name += '.json5'
    
    config_path = config_dir / config_name
    
    print(f"DEBUG: Loading and validating specific config: {config_path}")
    
    if not config_path.exists():
        print(f"DEBUG: Config file not found: {config_path}")
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    config = load_config(config_path)
    errors = validate_config(config)
    
    if errors:
        error_str = "\n".join(errors)
        print(f"DEBUG: Validation errors in {config_name}:\n{error_str}")
        raise ValueError(f"Invalid configuration in {config_name}:\n{error_str}")
    
    return config

def main():
    """
    Main function to validate configurations
    """
    print("OpenMind Configuration Validator")
    print("================================")
    
    # Validate all configuration files in the config directory
    config_dir = Path(__file__).parent.parent.parent / "config"
    print(f"\nValidating all config files in: {config_dir}")
    results = validate_all_configs(config_dir)
    print_validation_results(results)
    
    # Example of updating API keys if needed
    if OM1_API_KEY:
        print("\nUpdating API keys in configuration files...")
        update_results = update_all_api_keys(config_dir)
        for file_name, result in update_results.items():
            print(f"{file_name}: {result}")

if __name__ == "__main__":
    main()

