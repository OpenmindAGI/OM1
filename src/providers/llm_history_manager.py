import asyncio
import functools
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, List, Optional, TypeVar, Union

import openai

from llm import LLMConfig

from .io_provider import IOProvider

R = TypeVar("R")


@dataclass
class ChatMessage:
    role: str
    content: str


ACTION_MAP = {
    "emotion": "**** felt: {}.",
    "speak": "**** said: {}",
    "move": "**** performed this motion: {}.",
}


class LLMHistoryManager:
    def __init__(
        self,
        config: LLMConfig,
        client: Union[openai.AsyncClient, openai.OpenAI],
        system_prompt: str = "You are a helpful assistant that summarizes a succession of events and interactions accurately and concisely. You are watching a humanoid robot named **** interact with people and the world. Your goal is to help **** remember what she felt, saw, and heard, and how she responded to those inputs.",
        summary_command: str = "\nConsidering the new information, write an updated summary of the situation for ****. Emphasize information that **** needs to know to respond to people and situations in the best possible and most compelling way.",
    ):
        self.client = client

        # configuration
        self.config = config
        self.agent_name = self.config.agent_name
        self.system_prompt = system_prompt.replace("****", self.agent_name)
        self.summary_command = summary_command.replace("****", self.agent_name)

        # frame index
        self.frame_index = 0

        # task executor
        self._summary_task: Optional[asyncio.Task] = None

        # history buffer
        self.history: List[ChatMessage] = []

        # io provider
        self.io_provider = IOProvider()

    async def summarize_messages(self, messages: List[ChatMessage]) -> ChatMessage:
        """
        Summarize a list of messages using the OpenAI API.
        Returns a new message containing the summary.
        """
        try:

            logging.debug(f"All raw info: {messages} len{len(messages)}")

            summary_prompt = ""

            if len(messages) == 4:
                # the normal case - previous summary and new data
                # the previous summary
                summary_prompt += f"{messages[0].content}\n"
                # actions - already part of the summary - no need to add
                # summary_prompt += f"{messages[1].content}\n"
                summary_prompt += "\nNow, the following new information has arrived. "
                summary_prompt += f"{messages[2].content}\n"
                summary_prompt += f"{messages[3].content}\n"
            else:
                for msg in messages:
                    summary_prompt += f"{msg.content}\n"

            summary_prompt += self.summary_command

            # insert actual robot name
            summary_prompt = summary_prompt.replace("****", self.agent_name)

            logging.info(f"Information to summarize:\n{summary_prompt}")

            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": summary_prompt},
                ],
            )

            summary = response.choices[0].message.content
            return ChatMessage(role="assistant", content=f"Previously, {summary}")

        except Exception as e:
            logging.error(f"Error summarizing messages: {e}")
            return ChatMessage(role="system", content="Error summarizing state")

    async def start_summary_task(self, messages: List[ChatMessage]):
        """
        Start a new task to summarize the messages.
        """
        try:
            if self._summary_task and not self._summary_task.done():
                logging.info("Previous summary task still running")
                return

            self._summary_task = asyncio.create_task(self.summarize_messages(messages))

            def callback(task):
                try:
                    if not task.cancelled():
                        summary_message = task.result()
                        if summary_message.role == "assistant":
                            messages.clear()
                            messages.append(summary_message)
                            logging.info("Successfully summarized the state")
                        else:
                            raise Exception("Failed to summarize the state")
                except Exception as e:
                    logging.error(f"Error in summary task callback: {e}")
                    messages.pop(0) if messages else None
                    messages.pop(0) if messages else None

            self._summary_task.add_done_callback(callback)

        except Exception as e:
            logging.error(f"Error starting summary task: {e}")

    def get_messages(self) -> List[dict]:
        """
        Get messages in format required by OpenAI API.
        """
        return [{"role": msg.role, "content": msg.content} for msg in self.history]

    @staticmethod
    def update_history():
        def decorator(func: Callable[..., Awaitable[R]]) -> Callable[..., Awaitable[R]]:
            @functools.wraps(func)
            async def wrapper(self: Any, prompt: str, *args, **kwargs) -> R:

                if self._config.history_length == 0:
                    response = await func(self, prompt, [], *args, **kwargs)
                    self.history_manager.frame_index += 1
                    return response

                cycle = self.history_manager.frame_index
                logging.debug(f"LLM Tasking cycle debug tracker: {cycle}")

                formatted_inputs = "**** sensed the following: "
                for input_type, input_info in self.io_provider.inputs.items():
                    logging.info(f"LLM: {input_type}")
                    logging.info(f"LLM: {input_info}")
                    formatted_inputs += f"{input_type}: {input_info.input} | "

                # formatted_inputs = f"**** sensed the following: {" | ".join(f"{input_type}: {input_info.input}" for input_type, input_info in self.io_provider.inputs.items())}"
                inputs = ChatMessage(role="user", content=formatted_inputs)

                logging.debug(f"Inputs: {inputs}")
                self.history_manager.history.append(inputs)

                messages = self.history_manager.get_messages()
                logging.debug(f"messages:\n{messages}")
                # this advances the frame index
                response = await func(self, prompt, messages, *args, **kwargs)
                logging.debug(f"Response to parse:\n{response}")

                if response is not None:
                    logging.debug(f"Response to parse:\n{response}")
                    action_message = (
                        "Given that information, **** took these actions: "
                        + (
                            " | ".join(
                                ACTION_MAP[command.type].format(
                                    command.value if command.value else ""
                                )
                                for command in response.commands
                                if command.type in ACTION_MAP
                            )
                        )
                    )

                    self.history_manager.history.append(
                        ChatMessage(role="user", content=action_message)
                    )

                    if (
                        self.history_manager.config.history_length > 0
                        and len(self.history_manager.history)
                        > self.history_manager.config.history_length
                    ):
                        await self.history_manager.start_summary_task(
                            self.history_manager.history
                        )

                self.history_manager.frame_index += 1

                return response

            return wrapper

        return decorator
