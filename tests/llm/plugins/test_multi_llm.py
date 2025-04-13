from unittest.mock import patch

import pytest

from llm import LLMConfig
from llm.output_model import CortexOutputModel
from llm.plugins.multi_llm import MultiLLM


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
        "structured_output": '{"commands":[{"type":"move","value":"wag tail"},{"type":"move","value":"walk"},{"type":"speak","value":"Woof! Hello there! I see you!"},{"type":"emotion","value":"joy"}]}'
    }


@pytest.fixture
def mock_structured_output_response():
    """Mock API response with structured output matching our model"""
    return {"structured_output": {"result": "This is a structured result"}}


@pytest.fixture
def llm(config):
    return MultiLLM(CortexOutputModel, config)


def test_init_with_config(llm, config):
    """Test initialization with provided configuration"""
    assert llm._config.api_key == config.api_key
    assert llm.endpoint == "https://api.openmind.org/api/core/agent/robotic_team/runs"
    assert llm._config.model == config.model


def test_init_with_default_model():
    """Test that the MultiLLM uses the default model when not specified"""
    config = LLMConfig(api_key="test_key")
    llm = MultiLLM(CortexOutputModel, config)
    assert llm._config.model == "gemini-2.0-flash"


def test_init_empty_key():
    """Test initialization with missing API key"""
    config = LLMConfig(base_url="test_url")
    with pytest.raises(ValueError, match="config file missing api_key"):
        MultiLLM(CortexOutputModel, config)


@pytest.mark.asyncio
async def test_ask_structured_output(llm, mock_response):
    """Test handling of content-only response format"""
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_response

        result = await llm.ask("test prompt")
        assert result is not None


@pytest.mark.asyncio
async def test_ask_api_error(llm):
    """Test handling of API errors"""
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 500
        mock_post.return_value.text = "Internal Server Error"

        result = await llm.ask("test prompt")
        assert result is None


@pytest.mark.asyncio
async def test_ask_invalid_response(llm):
    """Test handling of invalid response format"""
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"invalid": "response"}

        result = await llm.ask("test prompt")
        assert result is None


@pytest.mark.asyncio
async def test_io_provider_timing(llm, mock_structured_output_response):
    """Test timing metrics collection"""
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_structured_output_response

        await llm.ask("test prompt")
        assert llm.io_provider.llm_start_time is not None
        assert llm.io_provider.llm_end_time is not None
        assert llm.io_provider.llm_end_time >= llm.io_provider.llm_start_time
