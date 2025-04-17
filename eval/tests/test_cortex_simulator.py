import asyncio
import os
import sys
import logging
import json5
import re
import argparse

# Add parent directories to path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_DIR = os.path.join(ROOT_DIR, "src")
EVAL_DIR = os.path.join(ROOT_DIR, "eval")
sys.path.insert(0, SRC_DIR)
sys.path.insert(0, EVAL_DIR)

from runtime.config import load_config
from runtime.cortex import CortexRuntime
from simulator import CortexSimulator

def extract_test_cases(config_name: str) -> list[dict]:
    """Extract test cases from system_prompt_examples in the configuration file."""
    config_path = os.path.join(ROOT_DIR, "config", f"{config_name}.json5")
    with open(config_path, "r") as f:
        config = json5.load(f)
    
    examples = config.get("system_prompt_examples", "")
    test_cases = []
    
    # Extract examples using regex
    pattern = r"If a person says '([^']+)', you might:\n(.*?)(?=\n\n|\Z)"
    matches = re.finditer(pattern, examples, re.DOTALL)
    
    for match in matches:
        prompt = match.group(1)
        actions_text = match.group(2)
        
        # Parse actions
        actions = []
        for line in actions_text.strip().split('\n'):
            if ':' in line:
                action_type, value = line.split(':', 1)
                action_type = action_type.strip().lower()
                value = value.strip().strip("'{}")
                actions.append({"type": action_type, "value": value})
        
        test_cases.append({
            "prompt": prompt,
            "expected": actions
        })
    
    return test_cases

async def test_single_prompt(simulator: CortexSimulator, prompt: str) -> None:
    """Test the simulator with a single prompt."""
    print(f"\n[Testing Single Prompt: {prompt}]")
    result = await simulator.simulate_tick(prompt)
    print("\nResult:")
    print(f"Prompt: {result['prompt']}")
    print("\nActions:")
    for action in result['actions']:
        print(f"- {action['type']}: {action['value']}")

async def test_conversation(simulator: CortexSimulator, test_cases: list[dict]) -> None:
    """Test the simulator with a sequence of prompts from test cases."""
    print("\n[Testing Conversation]")
    prompts = [case["prompt"] for case in test_cases]
    results = await simulator.simulate_conversation(prompts)
    print("\nConversation Results:")
    for i, (result, test_case) in enumerate(zip(results, test_cases), 1):
        print(f"\nTurn {i}:")
        print(f"Prompt: {result['prompt']}")
        print("Expected Actions:")
        for action in test_case["expected"]:
            print(f"- {action['type']}: {action['value']}")
        print("\nActual Actions:")
        for action in result['actions']:
            print(f"- {action['type']}: {action['value']}")

async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Test the Cortex Simulator with a configuration file')
    parser.add_argument('config_file', help='Configuration file name (without .json5 extension)')
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Load configuration and test cases
    config_name = args.config_file
    config = load_config(config_name)
    test_cases = extract_test_cases(config_name)
    
    runtime = CortexRuntime(config, debug_once=True)
    simulator = CortexSimulator(runtime)
    
    # Test scenarios
    if test_cases:
        print(f"Found {len(test_cases)} test cases from system prompt examples")
        # Test first case individually
        await test_single_prompt(simulator, test_cases[0]["prompt"])
        
        # Test all cases as a conversation
        await test_conversation(simulator, test_cases)
    else:
        print("No test cases found in system prompt examples.")

if __name__ == "__main__":
    asyncio.run(main()) 