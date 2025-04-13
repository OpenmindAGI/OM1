import json
import logging
import time
import typing as T

import requests
from pydantic import BaseModel

from llm import LLM, LLMConfig

R = T.TypeVar("R", bound=BaseModel)


class MultiLLM(LLM[R]):
    """
    MultiLLM implementation that sends requests to the robotic team endpoint.

    This plugin maintains the same output structure as other LLM plugins
    while routing requests through the agent-based robotic team.

    Parameters
    ----------
    output_model : Type[R]
        A Pydantic BaseModel subclass defining the expected response structure.
    config : LLMConfig
        Configuration object containing API settings. If not provided, defaults
        will be used.
    """

    def __init__(self, output_model: T.Type[R], config: LLMConfig = LLMConfig()):
        """
        Initialize the MultiLLM instance.

        Parameters
        ----------
        output_model : Type[R]
            Pydantic model class for response validation.
        config : LLMConfig, optional
            Configuration settings for the LLM.
        """
        super().__init__(output_model, config)

        if not config.api_key:
            raise ValueError("config file missing api_key")

        if not config.model:
            self._config.model = "gemini-2.0-flash"  # Use the exp version

        # Configure the API endpoint
        self.endpoint = "https://api.openmind.org/api/core/agent/robotic_team/runs"

    async def ask(
        self, prompt: str, messages: T.List[T.Dict[str, str]] = []
    ) -> R | None:
        """
        Send a prompt to the robotic team endpoint and get a structured response.

        Parameters
        ----------
        prompt : str
            The input prompt to send to the model.
        messages : List[Dict[str, str]]
            Message history to provide context.

        Returns
        -------
        R or None
            Parsed response matching the output_model structure, or None if
            parsing fails.
        """
        try:
            logging.debug(f"MultiLLM input: {prompt}")

            self.io_provider.llm_start_time = time.time()
            self.io_provider.set_llm_prompt(prompt)

            # Create a more detailed system prompt to ensure proper formatting
            system_message = {
                "role": "system",
                "content": f"You are a robotic control system. Respond with valid structured output for these commands. Output schema: {json.dumps(self._output_model.model_json_schema(), indent=2)}",
            }

            # Add system message at the beginning
            all_messages = [system_message]
            if messages:
                all_messages.extend(messages)
            all_messages.append({"role": "user", "content": prompt})

            headers = {
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            }
            request = {
                "message": prompt,
                "model": self._config.model,
                "messages": all_messages,
                "response_model": self._output_model.model_json_schema(),
                "structured_outputs": True,
            }

            response = requests.post(
                self.endpoint,
                json=request,
                headers=headers,
            )

            response_json = response.json()
            self.io_provider.llm_end_time = time.time()
            logging.info(f"Raw response: {response_json}")

            structured_output = response_json.get("structured_output")
            try:
                parsed_response = self._output_model.model_validate_json(
                    structured_output
                )
                logging.debug(f"MultiLLM structured output: {parsed_response}")
                return parsed_response
            except Exception as e:
                logging.error(f"Error validating structured response: {e}")
                return None

        except Exception as e:
            logging.error(f"Error during API request: {str(e)}")
            return None
