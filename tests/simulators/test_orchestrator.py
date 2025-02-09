import asyncio
from typing import List
from unittest.mock import Mock, patch

import pytest

from llm.output_model import Command, CommandArgument
from runtime.config import RuntimeConfig
from simulators.base import Simulator
from simulators.orchestrator import SimulatorOrchestrator


class MockSimulator(Simulator):
    def __init__(self, name: str):
        self.name = name
        self.tick_count = 0
        self.commands_received: List[Command] = []

    def tick(self):
        self.tick_count += 1

    def sim(self, commands: List[Command]):
        self.commands_received.extend(commands)


@pytest.fixture
def mock_config():
    config = Mock(spec=RuntimeConfig)
    simulator1 = MockSimulator("sim1")
    simulator2 = MockSimulator("sim2")
    config.simulators = [simulator1, simulator2]
    return config


@pytest.fixture
def orchestrator(mock_config):
    return SimulatorOrchestrator(mock_config)


@pytest.fixture
def test_command():
    """Create a test command with proper structure."""

    def _create_command(name="test", arg_name="test", arg_value="1"):
        return Command(
            name=name, arguments=[CommandArgument(name=arg_name, value=str(arg_value))]
        )

    return _create_command


@pytest.mark.asyncio
async def test_simulator_orchestrator_initialization(mock_config):
    """Test that SimulatorOrchestrator initializes correctly."""
    orchestrator = SimulatorOrchestrator(mock_config)
    assert orchestrator._config == mock_config
    assert len(orchestrator.promise_queue) == 0
    assert len(orchestrator._simulator_threads) == 0


@pytest.mark.asyncio
async def test_start_simulators(orchestrator):
    """Test that simulators are started in separate threads."""
    future = orchestrator.start()

    # Verify threads are created and started
    assert len(orchestrator._simulator_threads) == 2
    for thread in orchestrator._simulator_threads.values():
        assert thread.is_alive()
        assert thread.daemon is True

    assert isinstance(future, asyncio.Future)

    # Clean up threads
    for thread in orchestrator._simulator_threads.values():
        thread.join(timeout=1)


@pytest.mark.asyncio
async def test_promise_and_flush(mock_config):
    """Test sending commands to simulators and flushing promises."""
    # Create orchestrator with mock simulators
    orchestrator = SimulatorOrchestrator(mock_config)

    # Create a test command
    test_commands = [
        Command(name="test", arguments=[CommandArgument(name="test", value="1")])
    ]

    # Mock _promise_simulator to return immediately
    async def mock_promise_simulator(simulator, commands):
        simulator.sim(commands)
        return None

    orchestrator._promise_simulator = mock_promise_simulator

    # Send commands
    await orchestrator.promise(test_commands)

    # Verify promise queue length (one promise per simulator)
    assert len(orchestrator.promise_queue) == 2

    # Allow promises to complete
    await asyncio.sleep(0.1)

    # Flush promises
    done_promises, pending_promises = await orchestrator.flush_promises()

    # Verify promises were processed
    assert len(done_promises) == 2
    assert len(pending_promises) == 0

    # Verify that each simulator received the commands
    for simulator in mock_config.simulators:
        assert len(simulator.commands_received) == 1
        assert simulator.commands_received[0] == test_commands[0]


@pytest.mark.asyncio
async def test_promise_simulator(orchestrator, test_command):
    """Test sending commands to a single simulator."""
    test_commands = [test_command(name="test", arg_name="test", arg_value="1")]
    simulator = orchestrator._config.simulators[0]

    with patch("logging.debug") as mock_logging:
        result = await orchestrator._promise_simulator(simulator, test_commands)

        mock_logging.assert_called_with(
            f"Calling simulator {simulator.name} with commands {test_commands}"
        )
        assert result is None
        assert len(simulator.commands_received) == 1
        assert simulator.commands_received[0] == test_commands[0]


@pytest.mark.asyncio
async def test_concurrent_simulator_operations(orchestrator):
    """Test that multiple simulators can operate concurrently."""
    test_commands1 = [
        Command(name="test1", arguments=[CommandArgument(name="test", value="1")])
    ]
    test_commands2 = [
        Command(name="test2", arguments=[CommandArgument(name="test", value="2")])
    ]

    # Start simulators
    orchestrator.start()

    # Send multiple commands
    await asyncio.gather(
        orchestrator.promise(test_commands1), orchestrator.promise(test_commands2)
    )

    # Flush promises
    done_promises, pending_promises = await orchestrator.flush_promises()

    # Verify all promises are completed
    assert len(done_promises) == 4  # 2 commands * 2 simulators
    assert len(pending_promises) == 0

    # Verify simulators received both commands
    for simulator in orchestrator._config.simulators:
        received_commands = simulator.commands_received
        assert len(received_commands) == 2
        assert test_commands1[0] in received_commands
        assert test_commands2[0] in received_commands
