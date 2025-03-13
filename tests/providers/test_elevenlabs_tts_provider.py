import sys
from unittest.mock import MagicMock, Mock

import pytest

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


def test_initialization():
    provider = ElevenLabsTTSProvider(url="test_url")
    assert provider.running is False
    assert provider._thread is None


def test_start_stop():
    provider = ElevenLabsTTSProvider(url="test_url")
    provider.start()
    assert provider.running is True
    assert provider._thread is not None
    assert provider._thread.is_alive()

    provider.stop()
    assert provider.running is False
    provider._thread.join(timeout=1)
    assert not provider._thread.is_alive()


def test_register_callback():
    provider = ElevenLabsTTSProvider(url="test_url")
    callback = Mock()
    provider.register_tts_state_callback(callback)
    provider._audio_stream.set_tts_state_callback.assert_called_once_with(callback)


def test_multiple_start_calls():
    provider = ElevenLabsTTSProvider(url="test_url")
    provider.start()
    initial_thread = provider._thread
    provider.start()
    assert provider._thread is initial_thread
