import time
from unittest.mock import Mock, patch

import pytest
from PIL import Image

from inputs.plugins.vlm import Message, VlmInput


@pytest.fixture
def mock_io_provider():
    with patch("inputs.plugins.vlm.IOProvider") as mock:
        mock_instance = Mock()
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def vlm_input(mock_io_provider):
    return VlmInput()


def test_init(vlm_input, mock_io_provider):
    assert vlm_input.messages == []
    assert isinstance(vlm_input.io_provider, Mock)


@pytest.mark.asyncio
async def test_poll(vlm_input):
    result = await vlm_input._poll()
    assert isinstance(result, Image.Image)
    assert result.mode == "RGB"
    assert result.size == (100, 100)


@pytest.mark.asyncio
async def test_raw_to_text_conversion(vlm_input):
    test_image = Image.new("RGB", (100, 100), (255, 255, 255))
    result = await vlm_input._raw_to_text(test_image)

    assert isinstance(result, Message)
    assert isinstance(result.timestamp, float)
    assert isinstance(result.message, str)
    assert "I see" in result.message
    assert "people" in result.message
    assert "rocket" in result.message


@pytest.mark.asyncio
async def test_raw_to_text_buffer_management(vlm_input):
    test_image = Image.new("RGB", (100, 100), (255, 255, 255))

    assert len(vlm_input.messages) == 0
    await vlm_input.raw_to_text(test_image)
    assert len(vlm_input.messages) == 1

    first_message = vlm_input.messages[0]
    assert isinstance(first_message, Message)
    assert isinstance(first_message.message, str)


def test_formatted_latest_buffer_with_message(vlm_input):
    current_time = time.time()
    test_message = Message(timestamp=current_time, message="test detection")
    vlm_input.messages = [test_message]

    result = vlm_input.formatted_latest_buffer()

    assert result is not None
    assert "VlmInput INPUT" in result
    assert "START" in result
    assert "END" in result
    assert len(vlm_input.messages) == 0
    vlm_input.io_provider.add_input.assert_called_once_with(
        "VlmInput", "test detection", current_time
    )
