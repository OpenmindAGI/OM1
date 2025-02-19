import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

# Mock modules before importing from providers
mock_om1_speech = MagicMock()
mock_om1_speech.AudioOutputStream = MagicMock()
sys.modules["om1_speech"] = mock_om1_speech

mock_pyaudio = MagicMock()
mock_pyaudio.PyAudio = MagicMock()
mock_instance = MagicMock()
mock_instance.get_default_output_device_info.return_value = {
    "name": "Mock Speaker",
    "index": 0,
}
mock_pyaudio.PyAudio.return_value = mock_instance
sys.modules["pyaudio"] = mock_pyaudio

# Import after mocking
from providers.elevenlabs_tts_provider import ElevenLabsTTSProvider  # noqa: E402
from providers.singleton import singleton  # noqa: E402


@pytest.fixture(autouse=True)
def reset_singleton():
    singleton.instances = {}
    yield


@pytest.fixture(autouse=True)
def mock_audio_stream():
    with patch("providers.elevenlabs_tts_provider.ElevenLabsAudioOutputStream") as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock


def test_initialization(mock_audio_stream):
    provider = ElevenLabsTTSProvider(url="test_url")
    assert provider.running is False
    assert provider._thread is None
    mock_audio_stream.assert_called_once_with(
        url="test_url", device=None, device_name=None, headers=None
    )


def test_start_stop(mock_audio_stream):
    provider = ElevenLabsTTSProvider(url="test_url")
    provider.start()
    assert provider.running is True
    assert provider._thread is not None
    assert provider._thread.is_alive()

    provider.stop()
    assert provider.running is False
    provider._thread.join(timeout=1)
    assert not provider._thread.is_alive()


def test_register_callback(mock_audio_stream):
    provider = ElevenLabsTTSProvider(url="test_url")
    callback = Mock()
    provider.register_tts_state_callback(callback)
    mock_audio_stream.return_value.set_tts_state_callback.assert_called_once_with(
        callback
    )


def test_add_pending_message(mock_audio_stream):
    provider = ElevenLabsTTSProvider(url="test_url")
    provider.add_pending_message("test message")
    mock_audio_stream.return_value.add_request.assert_called_once_with(
        {
            "text": "test message",
            "voice_id": "JBFqnCBsd6RMkjVDRZzb",
            "model_id": "eleven_flash_v2_5",
            "output_format": "mp3_44100_128",
        }
    )


def test_multiple_start_calls(mock_audio_stream):
    provider = ElevenLabsTTSProvider(url="test_url")
    provider.start()
    initial_thread = provider._thread
    provider.start()
    assert provider._thread is initial_thread
