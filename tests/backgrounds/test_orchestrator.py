import asyncio
from unittest.mock import Mock

import pytest

from backgrounds.base import Background, BackgroundConfig
from backgrounds.orchestrator import BackgroundOrchestrator


class MockBackground(Background):
    def __init__(self, config: BackgroundConfig):
        super().__init__(config)

    def run(self):
        pass


@pytest.fixture
def mock_background():
    config = Mock(spec=BackgroundConfig)
    background1 = MockBackground(config=BackgroundConfig(name="bg1"))
    background2 = MockBackground(config=BackgroundConfig(name="bg2"))
    config.backgrounds = [background1, background2]
    return config


@pytest.fixture
def orchestrator(mock_background):
    return BackgroundOrchestrator(mock_background)


@pytest.mark.asyncio
async def test_background_orchestrator_initialization(mock_background):
    """Test that BackgroundOrchestrator initializes correctly."""
    orchestrator = BackgroundOrchestrator(mock_background)
    assert orchestrator._config == mock_background
    assert len(orchestrator._background_threads) == 0


@pytest.mark.asyncio
async def test_start_background(orchestrator):
    """Test that backgrounds are started in separate threads."""
    future = orchestrator.start()

    # Verify threads are created and started
    assert len(orchestrator._background_threads) == 2
    for thread in orchestrator._background_threads.values():
        assert thread.is_alive()
        assert thread.daemon is True

    assert isinstance(future, asyncio.Future)

    # Clean up threads
    for thread in orchestrator._background_threads.values():
        thread.join(timeout=1)
