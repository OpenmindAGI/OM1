from dataclasses import dataclass
from typing import Optional

import pytest

# Import the classes from your module (assuming it's named action_base.py)
from actions.base import (
    ActionConfig,
    ActionConnector,
    ActionImplementation,
    AgentAction,
    Interface,
)


# Example input and output types for testing
@dataclass
class TestInput:
    value: str


@dataclass
class TestOutput:
    result: str


# Test implementation of Interface
@dataclass
class TestInterface(Interface[TestInput, TestOutput]):
    input: TestInput
    output: TestOutput


# Test implementation of ActionImplementation
class TestActionImpl(ActionImplementation[TestInput, TestOutput]):
    async def execute(self, input_protocol: TestInput) -> TestOutput:
        return TestOutput(result=f"Processed: {input_protocol.value}")


# Test implementation of ActionConnector
class TestConnector(ActionConnector[TestOutput]):
    def __init__(self, config: ActionConfig):
        super().__init__(config)
        self.last_output: Optional[TestOutput] = None

    async def connect(self, input_protocol: TestOutput) -> None:
        self.last_output = input_protocol


@pytest.fixture
def action_config():
    return ActionConfig(param1="test_value", param2=123)


@pytest.fixture
def test_implementation(action_config):
    return TestActionImpl(action_config)


@pytest.fixture
def test_connector(action_config):
    return TestConnector(action_config)


@pytest.fixture
def agent_action(test_implementation, test_connector):
    return AgentAction(
        name="test_action",
        interface=TestInterface,
        implementation=test_implementation,
        connector=test_connector,
    )


@pytest.mark.asyncio
async def test_action_implementation_execute():
    config = ActionConfig(param1="test_value")
    implementation = TestActionImpl(config)
    test_input = TestInput(value="test_data")

    result = await implementation.execute(test_input)

    assert isinstance(result, TestOutput)
    assert result.result == "Processed: test_data"


@pytest.mark.asyncio
async def test_connector_connect():
    config = ActionConfig(param1="test_value")
    connector = TestConnector(config)
    test_output = TestOutput(result="test_result")

    await connector.connect(test_output)

    assert connector.last_output == test_output


@pytest.mark.asyncio
async def test_full_action_flow(agent_action):
    test_input = TestInput(value="test_data")

    # Execute the implementation
    output = await agent_action.implementation.execute(test_input)
    assert isinstance(output, TestOutput)

    # Connect the output
    await agent_action.connector.connect(output)
    assert isinstance(agent_action.connector, TestConnector)
    assert agent_action.connector.last_output == output


def test_action_config():
    config = ActionConfig(param1="value1", param2=123, param3=True)

    assert hasattr(config, "param1")
    assert config.param1 == "value1"
    assert hasattr(config, "param2")
    assert config.param2 == 123
    assert hasattr(config, "param3")
    assert config.param3 is True


def test_agent_action_structure(agent_action):
    assert agent_action.name == "test_action"
    assert agent_action.interface == TestInterface
    assert isinstance(agent_action.implementation, TestActionImpl)
    assert isinstance(agent_action.connector, TestConnector)
