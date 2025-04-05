from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel, Field

from llm import LLMConfig
from llm.plugins.multi_llm import ApiCommand, MultiLLM, RoboticTeamResponse


class DummyOutputModel(BaseModel):
    """Test output model matching other LLM plugins"""

    result: str = Field(..., description="The result from the LLM")


@pytest.fixture
def config():
    return LLMConfig(
        base_url="https://api.openmind.org/api/core",
        api_key="test_api_key",
        model="gemini-2.0-flash",
    )


@pytest.fixture
def mock_response():
    """Mock API response with markdown content"""
    return {
        "content": "The robot should move forward, then turn left, then continue straight."
    }


@pytest.fixture
def mock_api_commands_response():
    """Mock API response with commands array"""
    return {
        "commands": [
            {"command": "move", "args": "forward"},
            {"command": "speak", "args": "Hello there!"},
        ]
    }


@pytest.fixture
def mock_structured_output_response():
    """Mock API response with structured output matching our model"""
    return {"structured_output": {"result": "This is a structured result"}}


@pytest.fixture
def llm(config):
    return MultiLLM(DummyOutputModel, config)


@pytest.mark.asyncio
async def test_init_with_config(llm, config):
    """Test initialization with provided configuration"""
    assert llm.api_key == config.api_key
    assert llm.endpoint == "https://api.openmind.org/api/core/agent/robotic_team/runs"
    assert llm._config.model == config.model


@pytest.mark.asyncio
async def test_init_with_default_model():
    """Test that the MultiLLM uses the default model when not specified"""
    config = LLMConfig(api_key="test_key")
    llm = MultiLLM(DummyOutputModel, config)
    assert llm._config.model == "gemini-2.0-flash"


@pytest.mark.asyncio
async def test_init_empty_key():
    """Test initialization with missing API key"""
    config = LLMConfig(base_url="test_url")
    with pytest.raises(ValueError, match="config file missing api_key"):
        MultiLLM(DummyOutputModel, config)


@pytest.mark.asyncio
async def test_ask_content_response(llm, mock_response):
    """Test handling of content-only response format"""
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_post.return_value.__aenter__.return_value.status = 200
        mock_post.return_value.__aenter__.return_value.json = AsyncMock(
            return_value=mock_response
        )

        result = await llm.ask("test prompt")
        assert result is not None
        assert (
            result.result
            == "The robot should move forward, then turn left, then continue straight."
        )


@pytest.mark.asyncio
async def test_ask_api_commands(llm, mock_api_commands_response):
    """Test handling of API commands format"""
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_post.return_value.__aenter__.return_value.status = 200
        mock_post.return_value.__aenter__.return_value.json = AsyncMock(
            return_value=mock_api_commands_response
        )

        result = await llm.ask("test prompt")
        assert result is not None
        assert "move: forward" in result.result


@pytest.mark.asyncio
async def test_ask_structured_output(llm, mock_structured_output_response):
    """Test handling of structured output format"""
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_post.return_value.__aenter__.return_value.status = 200
        mock_post.return_value.__aenter__.return_value.json = AsyncMock(
            return_value=mock_structured_output_response
        )

        result = await llm.ask("test prompt")
        assert result is not None
        assert result.result == "This is a structured result"


@pytest.mark.asyncio
async def test_ask_api_error(llm):
    """Test handling of API errors"""
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_post.return_value.__aenter__.return_value.status = 500
        mock_post.return_value.__aenter__.return_value.text = AsyncMock(
            return_value="Internal Server Error"
        )

        result = await llm.ask("test prompt")
        assert result is None


@pytest.mark.asyncio
async def test_ask_invalid_response(llm):
    """Test handling of invalid response format"""
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_post.return_value.__aenter__.return_value.status = 200
        mock_post.return_value.__aenter__.return_value.json = AsyncMock(
            return_value={"invalid": "response"}
        )

        result = await llm.ask("test prompt")
        assert result is None


@pytest.mark.asyncio
async def test_io_provider_timing(llm, mock_response):
    """Test timing metrics collection"""
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_post.return_value.__aenter__.return_value.status = 200
        mock_post.return_value.__aenter__.return_value.json = AsyncMock(
            return_value=mock_response
        )

        await llm.ask("test prompt")
        assert llm.io_provider.llm_start_time is not None
        assert llm.io_provider.llm_end_time is not None
        assert llm.io_provider.llm_end_time >= llm.io_provider.llm_start_time
