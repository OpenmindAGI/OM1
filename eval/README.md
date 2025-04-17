# Evaluation System

This directory contains the evaluation system for testing and validating agent behaviors. The system is designed to be modular, maintainable, and independent of the production code.

## Directory Structure

```
eval/
├── evaluations/     # Contains evaluation logs
├── reports/        # Contains test reports and results
├── tests/          # Contains test scripts
├── test_cases/     # Contains test scenarios and evaluation scripts
├── evaluation_logger.py  # Logging utility for evaluations
└── simulator.py    # Simulator for testing agent behaviors
```

## Components

### 1. Simulator (`simulator.py`)
- A simulator that can run the production CortexRuntime and log results
- Provides methods for single prompt testing and conversation simulation
- Logs all interactions for later analysis

### 2. Evaluation Logger (`evaluation_logger.py`)
- Handles logging of evaluation results
- Creates both machine-friendly (JSONL) and human-readable logs
- Stores logs in the `evaluations/` directory

### 3. Test Scripts (`tests/`)
- Contains test scripts for different components
- Example: `test_cortex_simulator.py` for testing the simulator

### 4. Test Cases (`test_cases/`)
- Contains test scenarios and evaluation scripts
- Includes `evaluate.py` for running evaluations

### 5. Reports (`reports/`)
- Stores evaluation reports in JSON format
- Maintains an index of all reports
- Includes static assets for report visualization

## Usage

### Running Tests

1. Test the simulator with a specific configuration:
```bash
python eval/tests/test_cortex_simulator.py <config_name>
```
Example:
```bash
python eval/tests/test_cortex_simulator.py spot
```

2. Run evaluation scenarios:
```bash
python eval/test_cases/evaluate.py <test_file> <config_name>
```
Example:
```bash
python eval/test_cases/evaluate.py eval/test_cases/basic_test.json spot
```

### Test Results

- Evaluation logs are saved in `evaluations/` with timestamps
- Reports are generated in `reports/` with detailed test results
- The `reports/index.json` file maintains a list of all reports

## Test Cortex Simulator

The `test_cortex_simulator.py` script is a dedicated testing tool for the Cortex Simulator that:

### Features
- Tests both single prompts and conversation flows
- Extracts test cases from configuration files' system prompt examples
- Shows expected vs actual actions for comparison
- Provides detailed output for debugging and analysis

### Usage
```bash
python eval/tests/test_cortex_simulator.py <config_name>
```

### Output Format
```
[Testing Single Prompt: <prompt>]
Result:
Prompt: <prompt>
Actions:
- <action_type>: <action_value>

[Testing Conversation]
Conversation Results:
Turn 1:
Prompt: <prompt>
Expected Actions:
- <action_type>: <action_value>
Actual Actions:
- <action_type>: <action_value>
```

### Example Configuration
The script uses the `system_prompt_examples` from your configuration file (e.g., `spot.json5`) to generate test cases. For example:
```json5
"system_prompt_examples": "If a person says 'Give me your paw!', you might:
    Move: 'shake paw'
    Speak: 'Hello, let's shake paws!'
    Emotion: 'joy'"
```

## Adding New Tests

1. Create test cases in `test_cases/` directory
2. Use the simulator for testing agent behaviors
3. Run evaluations using the provided scripts
4. Check results in the reports directory

## Notes

- The evaluation system is designed to work independently of the production code
- All logs and reports are timestamped for easy tracking
- The system supports both single prompt testing and conversation simulation
- Test cases can be extracted from configuration files' system prompt examples 