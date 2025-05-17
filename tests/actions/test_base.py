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


@dataclass
class SampleInput:
    value: str


@dataclass
class SampleOutput:
    result: str


# Test implementation of Interface
@dataclass
class SampleInterface(Interface[SampleInput, SampleOutput]):
    input: SampleInput
    output: SampleOutput


# Test implementation of ActionImplementation
class SampleActionImpl(ActionImplementation[SampleInput, SampleOutput]):
    async def execute(self, input_protocol: SampleInput) -> SampleOutput:
        return SampleOutput(result=f"Processed: {input_protocol.value}")


# Test implementation of ActionConnector
class SampleConnector(ActionConnector[SampleOutput]):
    def __init__(self, config: ActionConfig):
        super().__init__(config)
        self.last_output: Optional[SampleOutput] = None

    async def connect(self, input_protocol: SampleOutput) -> None:
        self.last_output = input_protocol


@pytest.fixture
def action_config():
    return ActionConfig(param1="test_value", param2=123)


@pytest.fixture
def test_implementation(action_config):
    return SampleActionImpl(action_config)


@pytest.fixture
def test_connector(action_config):
    return SampleConnector(action_config)


@pytest.fixture
def agent_action(test_implementation, test_connector):
    return AgentAction(
        name="test_action",
        llm_label="test_llm_label",
        interface=SampleInterface,
        implementation=test_implementation,
        connector=test_connector,
    )


@pytest.mark.asyncio
async def test_action_implementation_execute():
    config = ActionConfig(param1="test_value")
    implementation = SampleActionImpl(config)
    test_input = SampleInput(value="test_data")

    result = await implementation.execute(test_input)

    assert isinstance(result, SampleOutput)
    assert result.result == "Processed: test_data"


@pytest.mark.asyncio
async def test_connector_connect():
    config = ActionConfig(param1="test_value")
    connector = SampleConnector(config)
    test_output = SampleOutput(result="test_result")

    await connector.connect(test_output)

    assert connector.last_output == test_output


@pytest.mark.asyncio
async def test_full_action_flow(agent_action):
    test_input = SampleInput(value="test_data")

    # Execute the implementation
    output = await agent_action.implementation.execute(test_input)
    assert isinstance(output, SampleOutput)

    # Connect the output
    await agent_action.connector.connect(output)
    assert isinstance(agent_action.connector, SampleConnector)
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
    assert agent_action.interface == SampleInterface
    assert isinstance(agent_action.implementation, SampleActionImpl)
    assert isinstance(agent_action.connector, SampleConnector)
