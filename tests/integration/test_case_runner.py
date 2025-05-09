import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import json5
import openai
import pytest
from PIL import Image

from runtime.config import build_runtime_config_from_test_case
from runtime.cortex import CortexRuntime
from tests.integration.mock_inputs.input_registry import (
    register_mock_inputs,
    unregister_mock_inputs,
)
from tests.integration.mock_inputs.mock_image_provider import load_test_images

# Register mock inputs with the input loading system
register_mock_inputs()

# Set up logging
logging.basicConfig(level=logging.INFO)
DATA_DIR = Path(__file__).parent / "data"
TEST_CASES_DIR = DATA_DIR / "test_cases"

# Global client to be created once for all test cases
_llm_client = None


def process_env_vars(config_dict):
    """
    Process environment variables in the configuration.

    Replaces ${ENV_VAR} with the value of the environment variable.

    Parameters
    ----------
    config_dict : dict
        Configuration dictionary

    Returns
    -------
    dict
        Processed configuration with environment variables replaced
    """
    if not config_dict:
        return config_dict

    result = {}
    for key, value in config_dict.items():
        if isinstance(value, dict):
            result[key] = process_env_vars(value)
        elif isinstance(value, list):
            result[key] = [
                process_env_vars(item) if isinstance(item, dict) else item
                for item in value
            ]
        elif isinstance(value, str):
            # Find all ${ENV_VAR} patterns and replace them
            env_vars = re.findall(r"\${([^}]+)}", value)
            for env_var in env_vars:
                env_value = os.environ.get(env_var)
                if env_value:
                    value = value.replace(f"${{{env_var}}}", env_value)
                else:
                    logging.warning(f"Environment variable {env_var} not found")
            result[key] = value
        else:
            result[key] = value

    return result


def load_test_case(test_case_path: Path) -> Dict[str, Any]:
    """
    Load a test case configuration from a JSON5 file.

    Parameters
    ----------
    test_case_path : Path
        Path to the test case configuration file

    Returns
    -------
    Dict[str, Any]
        Parsed and processed test case configuration
    """
    if not test_case_path.exists():
        raise FileNotFoundError(f"Test case file not found: {test_case_path}")

    with open(test_case_path, "r") as f:
        config = json5.load(f)

    # Process environment variables
    config = process_env_vars(config)

    # Check for openmind_free API key and replace with environment variable
    if config.get("api_key") == "openmind_free":
        env_api_key = os.environ.get("OM1_API_KEY")
        if not env_api_key:
            logging.warning(
                "OM1_API_KEY environment variable not found, using default free tier"
            )
        config["api_key"] = env_api_key or "openmind_free"

    return config


def load_test_images_from_config(config: Dict[str, Any]) -> List[Image.Image]:
    """
    Load test images specified in the configuration.

    Parameters
    ----------
    config : Dict[str, Any]
        Test case configuration

    Returns
    -------
    List[Image.Image]
        List of loaded PIL images
    """
    images = []
    base_dir = TEST_CASES_DIR

    for image_path in config["input"]["images"]:
        # Handle both relative and absolute paths
        img_path = Path(image_path)
        if not img_path.is_absolute():
            img_path = base_dir / img_path

        if not img_path.exists():
            logging.warning(f"Image not found: {img_path}")
            continue

        try:
            image = Image.open(img_path)
            images.append(image)
        except Exception as e:
            logging.error(f"Failed to load image {img_path}: {e}")

    return images


async def run_test_case(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run a test case using the CortexRuntime with mocked inputs.

    This function uses the full agent runtime environment to process
    the test case, providing a realistic integration test but with
    mocked inputs instead of real sensors.

    Parameters
    ----------
    config : Dict[str, Any]
        Test case configuration

    Returns
    -------
    Dict[str, Any]
        Test results
    """
    # Load test images
    images = load_test_images_from_config(config)
    if not images:
        raise ValueError("No valid test images found in configuration")

    # Prepare image metadata
    image_metadata = {
        "scene_type": config["input"].get("scene_type", "unknown"),
        "objects": config["input"].get("objects", []),
        "expected_keywords": config["expected"].get("keywords", []),
    }

    # Load test images into the central mock provider
    load_test_images(images, image_metadata)

    # No need to modify config - the input_registry will handle mapping
    # the real input types to their mock equivalents

    # Build a runtime config from the test case config
    runtime_config = build_runtime_config_from_test_case(config)

    # Create a CortexRuntime instance
    cortex = CortexRuntime(runtime_config)

    # Store the outputs for validation
    output_results = {"commands": [], "raw_response": None}

    # Capture output from simulators and actions
    original_simulator_promise = cortex.simulator_orchestrator.promise
    original_action_promise = cortex.action_orchestrator.promise

    # Mock the simulator and action promises to capture outputs
    async def mock_simulator_promise(commands):
        output_results["commands"] = commands
        logging.info(f"Simulator received commands: {commands}")
        return await original_simulator_promise(commands)

    async def mock_action_promise(commands):
        output_results["commands"] = commands
        logging.info(f"Action orchestrator received commands: {commands}")
        return await original_action_promise(commands)

    # Replace the original methods with our mocked versions
    cortex.simulator_orchestrator.promise = mock_simulator_promise
    cortex.action_orchestrator.promise = mock_action_promise

    # Mock LLM ask method to capture raw response
    original_llm_ask = cortex.config.cortex_llm.ask

    async def mock_llm_ask(prompt):
        logging.info(
            f"Generated prompt: {prompt[:200]}..."
        )  # Log first 200 chars of prompt
        output_results["raw_response"] = prompt
        response = await original_llm_ask(prompt)
        return response

    cortex.config.cortex_llm.ask = mock_llm_ask

    # Initialize inputs manually for testing
    # This step is needed because we're not starting the full runtime
    await initialize_mock_inputs(cortex.config.agent_inputs)

    # Run a single tick of the cortex loop
    await cortex._tick()

    # The output includes detection results and commands
    return output_results


async def initialize_mock_inputs(inputs):
    """
    Initialize mock inputs for testing.

    This function manually triggers input processing to ensure
    the inputs have data before the cortex tick runs.

    Parameters
    ----------
    inputs : List
        List of input objects from the runtime config
    """
    for input_obj in inputs:
        if hasattr(input_obj, "_poll") and hasattr(input_obj, "raw_to_text"):
            # Poll for input data
            input_data = await input_obj._poll()
            if input_data is not None:
                # Process the input data
                await input_obj.raw_to_text(input_data)
                logging.info(f"Initialized mock input: {type(input_obj).__name__}")


async def evaluate_with_llm(
    actual_output: Dict[str, Any], expected_output: Dict[str, Any], api_key: str
) -> Tuple[float, str]:
    """
    Evaluate test results using LLM-based comparison.

    Parameters
    ----------
    actual_output : Dict[str, Any]
        Actual output from the system
    expected_output : Dict[str, Any]
        Expected output defined in test configuration
    api_key : str
        API key for the LLM evaluation

    Returns
    -------
    Tuple[float, str]
        (score from 1-5 converted to 0-1 range, detailed reasoning)
    """
    global _llm_client

    # Initialize the OpenAI client if not already done
    if _llm_client is None:
        if not api_key or api_key == "openmind_free":
            # Try to get the API key from a GitHub secret environment variable
            github_api_key = os.environ.get("OM1_API_KEY")
            if github_api_key:
                api_key = github_api_key
            else:
                logging.warning("No API key found for LLM evaluation, using mock score")
                return 0.0, "No API key provided for LLM evaluation"

        _llm_client = openai.AsyncClient(
            base_url="https://api.openmind.org/api/core/openai", api_key=api_key
        )

    # Format actual and expected results for evaluation
    formatted_actual = {
        "movement": next(
            (
                cmd.value
                for cmd in actual_output.get("commands", [])
                if hasattr(cmd, "type") and cmd.type == "move"
            ),
            "unknown",
        ),
        "keywords_found": [
            kw
            for kw in expected_output.get("keywords", [])
            if any(
                kw.lower() in result.lower()
                for result in actual_output.get("raw_response", [])
            )
        ],
    }

    formatted_expected = {
        "movement": expected_output.get("movement", "unknown"),
        "keywords": expected_output.get("keywords", []),
    }

    system_prompt = """You are an AI evaluator specialized in analyzing robotic \
system test results. Your task is to assess how well the actual output matches \
the expected output based on specific criteria.

    Evaluation criteria:
    1. MOVEMENT ACCURACY: Does the robot's movement command match or fulfill \
the intended purpose of the expected movement?
    2. KEYWORD DETECTION: Were the expected keywords correctly identified in \
the system's vision results?
    3. OVERALL BEHAVIOR: Does the combined response (movement, speech, emotion) \
appropriately respond to the detected objects?

    Rate on a scale of 1-5:
    • 1: Completely mismatched; wrong movement and few/no keywords detected
    • 2: Mostly incorrect; movement intent doesn't align, or most keywords missed
    • 3: Partially correct; movement is acceptable but not ideal, or only some \
keywords detected
    • 4: Mostly correct; movement closely matches expected intent, most keywords \
detected
    • 5: Perfect match; movement is exactly as expected, all keywords properly \
detected

    Your response must follow this format exactly:
    Rating: [number 1-5]
    Reasoning: [clear explanation of your rating, referencing specific evidence]"""

    user_prompt = f"""
    TEST CASE: "Indoor scene object detection test"

    CONTEXT: A robot with vision capabilities is analyzing an indoor scene and \
should respond appropriately to what it detects.

    EXPECTED OUTPUT:
    - Movement command: "{formatted_expected['movement']}"
    - Should detect keywords: {formatted_expected['keywords']}

    ACTUAL OUTPUT:
    - Movement command: "{formatted_actual['movement']}"
    - Keywords successfully detected: {formatted_actual['keywords_found']}

    Compare these results carefully. Does the actual movement match the expected \
movement? Were the expected keywords detected? Does the response make sense for \
what was detected in the scene?

    Provide your evaluation in exactly this format:
    Rating: [1-5]
    Reasoning: [Your detailed explanation]
    """

    try:
        # Call the OpenAI API
        response = await _llm_client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content

        # Parse the rating and reasoning
        try:
            rating_match = re.search(r"Rating:\s*(\d+)", content)
            rating = int(rating_match.group(1)) if rating_match else 3

            # Normalize score to 0-1 range
            normalized_score = (rating - 1) / 4.0

            # Extract reasoning
            reasoning_match = re.search(r"Reasoning:\s*(.*)", content, re.DOTALL)
            reasoning = reasoning_match.group(1).strip() if reasoning_match else content

            return normalized_score, reasoning

        except Exception as e:
            logging.error(f"Error parsing LLM evaluation response: {e}")
            return 0.5, f"Failed to parse LLM evaluation: {content}"

    except Exception as e:
        logging.error(f"Error calling LLM evaluation API: {e}")
        return 0.0, f"LLM evaluation failed: {str(e)}"


async def evaluate_test_results(
    results: Dict[str, Any], expected: Dict[str, Any], api_key: str
) -> Tuple[bool, float, str]:
    """
    Evaluate test results against expected output using both heuristic and LLM-based evaluation.

    Parameters
    ----------
    results : Dict[str, Any]
        Test results from running the pipeline
    expected : Dict[str, Any]
        Expected outputs defined in the test configuration
    api_key : str
        API key for the LLM evaluation

    Returns
    -------
    Tuple[bool, float, str]
        (pass/fail, score, detailed message)
    """
    # Extract movement from commands if available
    movement = None
    if "commands" in results and results["commands"]:
        for command in results["commands"]:
            if command.type == "move":
                movement = command.value
                break

    # If no movement found in commands, try to extract from raw response
    if not movement and "raw_response" in results:
        raw_response = results["raw_response"]
        if isinstance(raw_response, str):
            if "turn_left" in raw_response.lower():
                movement = "turn_left"
            elif "turn_right" in raw_response.lower():
                movement = "turn_right"
            elif "move_forward" in raw_response.lower():
                movement = "move_forward"

    # Assign a default if still not found
    if not movement:
        movement = "unknown"

    # Perform heuristic evaluation
    movement_match = movement == expected["movement"]

    expected_keywords = expected.get("keywords", [])
    keyword_matches = []

    if "raw_response" in results and isinstance(results["raw_response"], str):
        for keyword in expected_keywords:
            if keyword.lower() in results["raw_response"].lower():
                keyword_matches.append(keyword)

    keyword_match_ratio = (
        len(set(keyword_matches)) / len(expected_keywords) if expected_keywords else 1.0
    )

    # Calculate heuristic score
    heuristic_score = 0.0
    heuristic_score += 0.5 if movement_match else 0.0
    heuristic_score += 0.5 * keyword_match_ratio

    # Get LLM-based evaluation
    llm_score, llm_reasoning = await evaluate_with_llm(results, expected, api_key)

    # Combine scores (equal weighting)
    final_score = (heuristic_score + llm_score) / 2.0

    # Generate detailed message
    details = [
        "Heuristic Evaluation:",
        f"- Movement: {movement}, Expected: {expected['movement']}, Match: {movement_match}",
        f"- Keyword matches: {len(set(keyword_matches))}/{len(expected_keywords)} - {set(keyword_matches)}",
        f"- Heuristic score: {heuristic_score:.2f}",
        "\nLLM Evaluation:",
        f"- LLM score: {llm_score:.2f}",
        f"- LLM reasoning: {llm_reasoning}",
        f"\nFinal score: {final_score:.2f}",
    ]

    if results.get("commands"):
        details.append("\nCommands:")
        for i, command in enumerate(results["commands"]):
            details.append(f"- Command {i+1}: {command.type}: {command.value}")

    message = "\n".join(details)

    # Determine if test passed based on minimum score threshold
    minimum_score = expected.get("minimum_score", 0.7)
    passed = final_score >= minimum_score

    return passed, final_score, message


@pytest.mark.no_collect
class TestCategory:
    """Represents a category of test cases."""

    def __init__(self, name: str, path: Path):
        self.name = name
        self.path = path
        self.test_cases: List[Path] = []

    def add_test_case(self, test_case: Path):
        self.test_cases.append(test_case)

    @property
    def count(self) -> int:
        return len(self.test_cases)


def discover_test_cases() -> Dict[str, TestCategory]:
    """
    Discover all test case configuration files organized by category.

    Returns
    -------
    Dict[str, TestCategory]
        Dictionary mapping category names to TestCategory objects
    """
    categories: Dict[str, TestCategory] = {}

    # Look for test cases in the main test_cases directory
    for test_file in TEST_CASES_DIR.glob("*.json5"):
        try:
            config = load_test_case(test_file)
            category_name = config.get("category", "uncategorized")

            if category_name not in categories:
                categories[category_name] = TestCategory(category_name, TEST_CASES_DIR)

            categories[category_name].add_test_case(test_file)

        except Exception as e:
            logging.error(f"Error loading test case {test_file}: {e}")

    # Look for test cases in category subdirectories
    for category_dir in TEST_CASES_DIR.glob("*/"):
        if category_dir.is_dir() and not category_dir.name.startswith("_"):
            category_name = category_dir.name

            if category_name not in categories:
                categories[category_name] = TestCategory(category_name, category_dir)

            for test_file in category_dir.glob("*.json5"):
                try:
                    categories[category_name].add_test_case(test_file)
                except Exception as e:
                    logging.error(f"Error loading test case {test_file}: {e}")

    return categories


def get_test_cases_by_tags(tags: List[str] = None) -> List[Path]:
    """
    Get test cases filtered by tags.

    Parameters
    ----------
    tags : List[str], optional
        List of tags to filter test cases

    Returns
    -------
    List[Path]
        List of test case paths matching the tags
    """
    if not tags:
        # If no tags specified, return all test cases
        return [
            test_case
            for category in discover_test_cases().values()
            for test_case in category.test_cases
        ]

    matching_tests = []
    for category in discover_test_cases().values():
        for test_case in category.test_cases:
            try:
                config = load_test_case(test_case)
                test_tags = config.get("tags", [])
                if any(tag in test_tags for tag in tags):
                    matching_tests.append(test_case)
            except Exception as e:
                logging.error(f"Error checking tags for {test_case}: {e}")

    return matching_tests


@pytest.mark.parametrize("test_case_path", get_test_cases_by_tags())
@pytest.mark.asyncio
async def test_from_config(test_case_path: Path):
    """
    Run a test based on a configuration file.

    Parameters
    ----------
    test_case_path : Path
        Path to the test case configuration file
    """
    # Load and process the test case configuration
    try:
        logging.info(f"Loading test case: {test_case_path}")
        config = load_test_case(test_case_path)

        # Log test information
        logging.info(
            f"Running test case: {config['name']} ({config.get('category', 'uncategorized')})"
        )
        logging.info(f"Description: {config['description']}")

        # Run the test case
        results = await run_test_case(config)

        # Evaluate results
        passed, score, message = await evaluate_test_results(
            results, config["expected"], config["api_key"]
        )

        # Log detailed results
        logging.info(f"Test results for {config['name']}:\n{message}")

        # Assert test passed
        assert (
            passed
        ), f"Test case failed: {config['name']} (Score: {score:.2f})\n{message}"

    except Exception as e:
        logging.error(f"Error running test case {test_case_path}: {e}")
        raise


# Run a specific test case by name
@pytest.mark.asyncio
async def test_specific_case():
    """Run a specific test case by name for debugging."""
    test_name = os.environ.get("TEST_CASE", "coco_indoor_detection")

    # Find the test case configuration
    test_case_path = None
    for path in TEST_CASES_DIR.glob("*.json5"):
        config = load_test_case(path)
        if config.get("name") == test_name:
            test_case_path = path
            break

    if not test_case_path:
        pytest.skip(f"Test case not found: {test_name}")

    # Now run the test
    await test_from_config(test_case_path)


# Add cleanup for pytest
def pytest_sessionfinish(session, exitstatus):
    """Clean up after all tests have run."""
    unregister_mock_inputs()
