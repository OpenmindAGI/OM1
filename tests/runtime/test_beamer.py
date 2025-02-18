from unittest.mock import Mock, patch

import pytest

from runtime.beamer import send_beams_to_beamer, setup_beamer

API_KEY = "test-api-key"
UUID = "test-uuid"
BASE_CONFIG = {
    "cache": True,
    "beamer_url": "https://api.openmind.org/api/core/beamer",
    "other_config": "value",
}


@pytest.fixture
def mock_requests():
    with patch("requests.post") as mock_post:
        yield mock_post


@pytest.fixture
def mock_logging():
    with patch("logging.info") as mock_info, patch("logging.error") as mock_error:
        yield {"info": mock_info, "error": mock_error}


def test_setup_beamer_with_cache_enabled(mock_requests, mock_logging):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_requests.return_value = mock_response
    config = BASE_CONFIG.copy()

    result = setup_beamer(API_KEY, UUID, config)

    assert result is True
    assert "beamer_url" not in config
    mock_requests.assert_called_once_with(
        BASE_CONFIG["beamer_url"],
        json=config,
        headers={
            "x-api-key": API_KEY,
            "Content-Type": "application/json",
            "x-uuid": UUID,
        },
    )
    mock_logging["info"].assert_called_once()


def test_setup_beamer_with_cache_disabled():
    config = BASE_CONFIG.copy()
    config["cache"] = False

    result = setup_beamer(API_KEY, UUID, config)

    assert result is False
    assert "beamer_url" not in config


def test_setup_beamer_with_empty_api_key():
    config = BASE_CONFIG.copy()

    result = setup_beamer("", UUID, config)

    assert result is False
    assert "beamer_url" not in config


def test_setup_beamer_with_none_api_key():
    config = BASE_CONFIG.copy()

    result = setup_beamer(None, UUID, config)

    assert result is False
    assert "beamer_url" not in config


def test_send_beams_to_beamer_success(mock_requests, mock_logging):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_requests.return_value = mock_response
    config = BASE_CONFIG.copy()

    result = send_beams_to_beamer(API_KEY, UUID, config)

    assert result is True
    mock_logging["info"].assert_called_once()


def test_send_beams_to_beamer_failure(mock_requests, mock_logging):
    mock_response = Mock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    mock_requests.return_value = mock_response
    config = BASE_CONFIG.copy()

    result = send_beams_to_beamer(API_KEY, UUID, config)

    assert result is False
    mock_logging["error"].assert_called_once()


def test_send_beams_to_beamer_exception(mock_requests, mock_logging):
    mock_requests.side_effect = Exception("Connection error")
    config = BASE_CONFIG.copy()

    result = send_beams_to_beamer(API_KEY, UUID, config)

    assert result is False
    mock_logging["error"].assert_called_once()


def test_send_beams_to_beamer_custom_url(mock_requests):
    # Arrange
    mock_response = Mock()
    mock_response.status_code = 200
    mock_requests.return_value = mock_response
    config = BASE_CONFIG.copy()
    config["beamer_url"] = "https://custom.api.url/beamer"

    result = send_beams_to_beamer(API_KEY, UUID, config)

    assert result is True
    mock_requests.assert_called_once_with(
        "https://custom.api.url/beamer",
        json=config,
        headers={
            "x-api-key": API_KEY,
            "Content-Type": "application/json",
            "x-uuid": UUID,
        },
    )
