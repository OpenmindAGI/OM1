from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel

from llm import LLMConfig
from llm.plugins.gemini_llm import GeminiLLM


class DummyOutputModel(BaseModel):
    test_field: str


@pytest.fixture
def config():
    return LLMConfig(base_url="test_url/", api_key="test_key", model="test_model")


@pytest.fixture
def mock_response():
    """Fixture providing a valid mock API response"""
    response = MagicMock()
    response.choices = [
        MagicMock(message=MagicMock(content='{"test_field": "success"}'))
    ]
    return response


@pytest.fixture
def llm(config):
    return GeminiLLM(DummyOutputModel, config)


@pytest.mark.asyncio
async def test_init_empty_key():
    """Test fallback API key when no credentials provided"""
    config = LLMConfig(base_url="test_url")
    with pytest.raises(ValueError, match="config file missing api_key"):
        GeminiLLM(DummyOutputModel, config)


@pytest.mark.asyncio
async def test_ask_api_error(llm):
    """Test error handling for API exceptions"""
    with pytest.MonkeyPatch.context() as m:
        m.setattr(
            llm._client.chat.completions,
            "create",
            MagicMock(side_effect=Exception("API error")),
        )

        result = await llm.ask("test prompt")
        assert result is None


@pytest.mark.asyncio
async def test_io_provider_timing(llm, mock_response):
    """Test timing metrics collection"""
    with pytest.MonkeyPatch.context() as m:
        m.setattr(
            llm._client.chat.completions,
            "create",
            MagicMock(return_value=mock_response),
        )
        await llm.ask("test prompt")
        assert llm.io_provider.llm_start_time is not None
        assert llm.io_provider.llm_end_time is not None
        assert llm.io_provider.llm_end_time >= llm.io_provider.llm_start_time - 0.1


@pytest.mark.asyncio
async def test_init_with_config(llm, config):
    assert llm._client.base_url == config.base_url
    assert llm._client.api_key == config.api_key
    assert llm._config.model == config.model


@pytest.mark.asyncio
async def test_ask_success(llm, mock_response):
    """Test successful API request and response parsing"""
    with pytest.MonkeyPatch.context() as m:
        m.setattr(
            llm._client.chat.completions,
            "create",
            AsyncMock(return_value=mock_response),
        )

        result = await llm.ask("test prompt")
        print("result", result)
        assert isinstance(result, DummyOutputModel)
        assert result.test_field == "success"


@pytest.mark.asyncio
async def test_ask_invalid_json(llm):
    """Test handling of invalid JSON response"""
    invalid_response = MagicMock()
    invalid_response.choices = [MagicMock(message=MagicMock(content="invalid"))]

    with pytest.MonkeyPatch.context() as m:
        m.setattr(
            llm._client.chat.completions,
            "create",
            MagicMock(return_value=invalid_response),
        )

        result = await llm.ask("test prompt")
        assert result is None
