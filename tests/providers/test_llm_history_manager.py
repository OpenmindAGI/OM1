import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from providers.llm_history_manager import ChatMessage, LLMHistoryManager


@pytest.fixture
def llm_config():
    config = MagicMock()
    config.model = "gpt-4o"
    config.history_length = 5
    config.agent_name = "Test Robot"
    return config


@pytest.fixture
def openai_client():
    client = AsyncMock()
    response = AsyncMock()
    response.choices = [AsyncMock()]
    response.choices[0].message.content = "This is a test summary"
    client.chat.completions.create.return_value = response
    return client


@pytest.fixture
def history_manager(llm_config, openai_client):
    return LLMHistoryManager(llm_config, openai_client)


@pytest.mark.asyncio
async def test_summarize_messages_success(history_manager):
    # Create test messages
    messages = [
        ChatMessage(role="assistant", content="Previous summary"),
        ChatMessage(role="user", content="New input"),
        ChatMessage(role="user", content="Action taken"),
    ]

    # Test successful summarization
    result = await history_manager.summarize_messages(messages)
    assert result.role == "assistant"
    assert "Previously, This is a test summary" == result.content


@pytest.mark.asyncio
async def test_summarize_messages_empty(history_manager):
    # Test with empty messages
    result = await history_manager.summarize_messages([])
    assert result.role == "system"
    assert "No history to summarize" == result.content


@pytest.mark.asyncio
async def test_summarize_messages_api_error(history_manager):
    # Mock API error
    history_manager.client.chat.completions.create.side_effect = Exception("API Error")

    messages = [ChatMessage(role="user", content="Test")]
    result = await history_manager.summarize_messages(messages)

    assert result.role == "system"
    assert "Error summarizing state" == result.content


@pytest.mark.asyncio
async def test_start_summary_task(history_manager):
    # Create test messages that we'll modify in-place
    messages = [
        ChatMessage(role="assistant", content="Previous summary"),
        ChatMessage(role="user", content="New input"),
        ChatMessage(role="user", content="Action taken"),
    ]

    # Replace summarize_messages with a mock
    history_manager.summarize_messages = AsyncMock()
    history_manager.summarize_messages.return_value = ChatMessage(
        role="assistant", content="New summary"
    )

    # Run the summary task
    await history_manager.start_summary_task(messages)

    # Let the task and callback complete
    await asyncio.sleep(0.1)

    # Verify the task was created
    assert history_manager._summary_task is not None

    # Let the event loop process the callback
    await asyncio.sleep(0.1)

    # Because we mocked summarize_messages, the callback should have run
    # and updated the messages list
    assert len(messages) == 1
    assert messages[0].role == "assistant"
    assert "New summary" == messages[0].content


@pytest.mark.asyncio
async def test_start_summary_task_empty_messages(history_manager):
    # Test with empty messages
    await history_manager.start_summary_task([])
    assert history_manager._summary_task is None


@pytest.mark.asyncio
async def test_start_summary_task_error_handling(history_manager):
    messages = [
        ChatMessage(role="user", content="Test message"),
    ]

    # Mock error in summarization
    history_manager.summarize_messages = AsyncMock()
    history_manager.summarize_messages.return_value = ChatMessage(
        role="system", content="Error: API service unavailable"
    )

    # Run the summary task
    await history_manager.start_summary_task(messages)

    # Let the task and callback complete
    await asyncio.sleep(0.1)

    assert len(messages) == 0
