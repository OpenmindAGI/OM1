# Configuration File Validation

This feature adds schema validation for all configuration files in the `/config/` directory. It ensures that configuration files follow the expected structure and contain all required fields.

## Requirements

The validation system requires the `jsonschema` package to be installed. You can install it manually using one of these methods:

### Using uv (Recommended for OM1 Project)

```bash
uv pip install jsonschema
```

### Using pip

```bash
pip install jsonschema
# or
python -m pip install jsonschema
```

### Installing All Requirements

```bash
# With uv
uv pip install -r requirements.txt

# With pip
pip install -r requirements.txt
```

## Validating Configuration Files

### Command Line Interface

You can validate configuration files using the CLI:

```bash
# Validate a specific configuration file
python -m src.run validate open_ai

# Validate all configuration files
python -m src.run validate
```

### Standalone Scripts

Two standalone scripts are provided for validation:

1. Root-level script (simple):
```bash
python validate_configs.py
```

2. Scripts directory script (more detailed):
```bash
python scripts/validate_configs.py
```

Both scripts will check for dependencies and offer to install them if they're missing, or provide clear instructions on how to install them manually.

### Environment Issues

If you encounter import errors:

1. Make sure you're using the correct Python environment (check for `.venv` or other virtual environments)
2. Install dependencies using the appropriate package manager:

   ```bash
   # For OM1 with uv
   uv pip install jsonschema
   
   # For standard Python environments
   pip install jsonschema
   
   # For user-level installation (not recommended)
   pip install jsonschema --user
   ```

3. Run the validation scripts from the project root directory

## Schema Definition

The schema is defined in `src/runtime/schema_validator.py` and includes:

- Required fields validation
- Type checking for values
- Range validation for numeric fields
- Structure validation for nested objects

## Adding New Configuration Files

When adding new configuration files, make sure they adhere to the schema defined in `src/runtime/schema_validator.py`. All configuration files must have the following required fields:

- `hertz`: Number >= 0
- `name`: String
- `system_prompt_base`: String
- `system_governance`: String
- `system_prompt_examples`: String
- `agent_inputs`: Array of input configurations
- `cortex_llm`: LLM configuration
- `agent_actions`: Array of action configurations

## Extending the Schema

If you need to add new fields to the schema, update the `CONFIG_SCHEMA` dictionary in `src/runtime/schema_validator.py`. 