#!/usr/bin/env python
"""
Script to validate configuration files against the schema.
"""

import os
import sys
import logging
from pathlib import Path

# Try to import jsonschema
missing_jsonschema = False
try:
    import jsonschema
except ImportError:
    missing_jsonschema = True
    print("jsonschema module not found.")
    print("Please install it using one of these commands:")
    print("  uv pip install jsonschema")
    print("  pip install jsonschema")
    print("  python -m pip install jsonschema")
    print("\nAlternatively, install all requirements:")
    print("  uv pip install -r requirements.txt")
    print("  pip install -r requirements.txt")
    
    # Don't exit immediately, give a chance to manually install
    choice = input("\nTry to install automatically? (y/n): ")
    if choice.lower() == 'y':
        try:
            import subprocess
            # Try uv first (since it seems to be the environment being used)
            try:
                print("Trying to install with uv...")
                subprocess.check_call(["uv", "pip", "install", "jsonschema"])
            except (FileNotFoundError, subprocess.CalledProcessError):
                # Fall back to pip
                print("Trying to install with pip...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "jsonschema"])
            
            print("jsonschema installed successfully")
            import jsonschema
            missing_jsonschema = False
        except Exception as e:
            print(f"Failed to install jsonschema: {str(e)}")
            print("Please install it manually and try again.")
            sys.exit(1)

if missing_jsonschema:
    sys.exit(1)

# Try to import json5
missing_json5 = False
try:
    import json5
except ImportError:
    missing_json5 = True
    print("json5 module not found. Please install it manually.")
    print("  uv pip install json5")
    print("  pip install json5")
    sys.exit(1)

# Add the src directory to the Python path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from src.runtime.schema_validator import validate_config
except ImportError:
    print("Error: Could not import schema_validator module.")
    print("Make sure you're running this script from the project root directory.")
    sys.exit(1)

def main():
    """Main entry point."""
    logging.basicConfig(level=logging.INFO)
    
    # Get the project root directory
    config_dir = Path("config")
    
    if not config_dir.exists():
        print(f"Error: Config directory '{config_dir}' not found.")
        print("Make sure you're running this script from the project root directory.")
        return 1
    
    # Validate all configuration files
    print(f"Validating configuration files in {config_dir}...")
    
    config_files = list(config_dir.glob("*.json5"))
    if not config_files:
        print(f"No .json5 configuration files found in {config_dir}")
        return 1
    
    has_errors = False
    for config_file in config_files:
        try:
            with open(config_file, "r") as f:
                config_data = json5.load(f)
            
            errors = validate_config(config_data)
            if errors:
                has_errors = True
                print(f"❌ Configuration file {config_file.name} has validation errors:")
                for error in errors:
                    print(f"  - {error}")
            else:
                print(f"✅ Configuration file {config_file.name} is valid.")
        except Exception as e:
            has_errors = True
            print(f"❌ Error validating {config_file.name}: {str(e)}")
    
    return 1 if has_errors else 0

if __name__ == "__main__":
    sys.exit(main()) 