from dataclasses import dataclass
from typing import List
from unittest.mock import patch

from fuser import Fuser
from inputs.base import Sensor
from providers.io_provider import IOProvider


@dataclass
class MockSensor(Sensor):
    def formatted_latest_buffer(self):
        return "test input"


@dataclass
class MockAction:
    name: str
    llm_label: str = None


@dataclass
class MockConfig:
    system_prompt_base: str = "system prompt base"
    system_governance: str = "system governance"
    system_prompt_examples: str = "system prompt examples"
    agent_actions: List[MockAction] = None

    def __post_init__(self):
        if self.agent_actions is None:
            self.agent_actions = []


def test_fuser_initialization():
    config = MockConfig()
    io_provider = IOProvider()

    with patch("fuser.IOProvider", return_value=io_provider):
        fuser = Fuser(config)
        assert fuser.config == config
        assert fuser.io_provider == io_provider


@patch("time.time")
def test_fuser_timestamps(mock_time):
    mock_time.return_value = 1000
    config = MockConfig()
    io_provider = IOProvider()

    with patch("fuser.IOProvider", return_value=io_provider):
        fuser = Fuser(config)
        fuser.fuse([], [])
        assert io_provider.fuser_start_time == 1000
        assert io_provider.fuser_end_time == 1000


@patch("fuser.describe_action")
def test_fuser_with_inputs_and_actions(mock_describe):
    mock_describe.return_value = "action description"
    config = MockConfig(agent_actions=[MockAction("action1"), MockAction("action2")])
    inputs = [MockSensor()]
    io_provider = IOProvider()

    with patch("fuser.IOProvider", return_value=io_provider):
        fuser = Fuser(config)
        result = fuser.fuse(inputs, [])

        system_prompt = (
            "BASIC CONTEXT:\n"
            + config.system_prompt_base
            + "\n"
            + "\nLAWS:\n"
            + config.system_governance
            + "\n"
            + "\nEXAMPLES:\n"
            + config.system_prompt_examples
        )
        expected = f"{system_prompt}\n\ntest input\n\nAVAILABLE ACTIONS:\naction description\n\n\naction description\n\nWhat will you do? Command: "
        assert result == expected
        assert mock_describe.call_count == 2
        assert io_provider.fuser_system_prompt == system_prompt
        assert io_provider.fuser_inputs == "test input"
        assert (
            io_provider.fuser_available_actions
            == "AVAILABLE ACTIONS:\naction description\n\n\naction description\n\nWhat will you do? Command: "
        )
