from unittest.mock import patch

import pytest

from llm import LLMConfig
from llm.output_model import CortexOutputModel
from llm.plugins.multi_llm_healthy import MultiLLMHealthy


@pytest.fixture
def config():
    return LLMConfig(
        base_url="https://api.openmind.org/api/core",
        api_key="test_api_key",
        model="gpt-4.1-nano",
    )


@pytest.fixture
def config_with_question_states():
    question_states = {
        "current_question_index": 1,
        "states": [
            {
                "index": 0,
                "question": "How are you feeling today?",
                "answer": "I feel good",
                "status": "answered",
            },
            {
                "index": 1,
                "question": "Any pain or discomfort?",
                "answer": "",
                "status": "not_asked",
            },
        ],
    }
    return LLMConfig(
        base_url="https://api.openmind.org/api/core",
        api_key="test_api_key",
        model="gpt-4.1-nano",
        question_states=question_states,
    )


@pytest.fixture
def mock_response():
    """Mock API response with markdown content"""
    return {
        "content": '{"actions":[{"type":"move","value":"wag tail"},{"type":"move","value":"walk"},{"type":"speak","value":"Hello! How can I help with your medical question?"},{"type":"emotion","value":"concern"}]}',
        "extra": {
            "question_states": {
                "current_question_index": 2,
                "states": [
                    {
                        "index": 0,
                        "question": "How are you feeling today?",
                        "answer": "I feel good",
                        "status": "answered",
                    },
                    {
                        "index": 1,
                        "question": "Any pain or discomfort?",
                        "answer": "No pain",
                        "status": "answered",
                    },
                    {
                        "index": 2,
                        "question": "When did symptoms start?",
                        "answer": "",
                        "status": "not_asked",
                    },
                ],
            }
        },
    }


@pytest.fixture
def mock_structured_output_response():
    """Mock API response with structured output matching our model"""
    return {
        "content": {"result": "This is a structured medical result"},
        "extra": {
            "question_states": {
                "current_question_index": 2,
                "states": [
                    {
                        "index": 0,
                        "question": "How are you feeling today?",
                        "answer": "I feel good",
                        "status": "answered",
                    },
                    {
                        "index": 1,
                        "question": "Any pain or discomfort?",
                        "answer": "No pain",
                        "status": "answered",
                    },
                    {
                        "index": 2,
                        "question": "When did symptoms start?",
                        "answer": "",
                        "status": "not_asked",
                    },
                ],
            }
        },
    }


@pytest.fixture
def llm(config):
    return MultiLLMHealthy(CortexOutputModel, config)


@pytest.fixture
def llm_with_question_states(config_with_question_states):
    return MultiLLMHealthy(CortexOutputModel, config_with_question_states)


def test_init_with_config(llm, config):
    """Test initialization with provided configuration"""
    assert llm._config.api_key == config.api_key
    assert llm.endpoint == "https://api.openmind.org/api/core/agent/medical"
    assert llm._config.model == config.model


def test_init_with_question_states(
    llm_with_question_states, config_with_question_states
):
    """Test initialization with question states in config"""
    # Test that the question_states are correctly stored in config
    # The io_provider doesn't get populated until ask() is called
    assert hasattr(llm_with_question_states._config, "question_states")
    assert (
        llm_with_question_states._config.question_states
        == config_with_question_states.question_states
    )


def test_init_with_default_model():
    """Test that the MultiLLMHealthy uses the default model when not specified"""
    config = LLMConfig(api_key="test_key")
    llm = MultiLLMHealthy(CortexOutputModel, config)
    assert llm._config.model == "gpt-4.1-nano"


def test_init_empty_key():
    """Test initialization with missing API key"""
    config = LLMConfig(base_url="test_url")
    with pytest.raises(ValueError, match="config file missing api_key"):
        MultiLLMHealthy(CortexOutputModel, config)


@pytest.mark.asyncio
async def test_ask_structured_output(llm, mock_response):
    """Test handling of content-only response format"""
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_response

        result = await llm.ask("test prompt")
        assert result is not None
        assert (
            llm.io_provider.get_dynamic_variable("question_states")
            == mock_response["extra"]["question_states"]
        )


@pytest.mark.asyncio
async def test_ask_with_question_state(llm_with_question_states, mock_response):
    """Test that question state is included in request and updated from response"""
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_response

        # Capture the request to verify question_state is included
        await llm_with_question_states.ask("test prompt")

        # Verify the question state was sent in the request
        request_json = mock_post.call_args[1]["json"]
        assert "question_state" in request_json
        # Now we no longer assert exact equality since it can be updated
        # during processing, but we verify it was included
        assert request_json["question_state"] is not None
        assert "current_question_index" in request_json["question_state"]
        assert "states" in request_json["question_state"]

        # Verify question state was updated from response
        assert (
            llm_with_question_states.io_provider.get_dynamic_variable("question_states")
            == mock_response["extra"]["question_states"]
        )


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
