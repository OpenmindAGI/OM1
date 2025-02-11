import logging
import time
import typing as T

import openai
from pydantic import BaseModel

from llm import LLM, LLMConfig

R = T.TypeVar("R", bound=BaseModel)


class DeepSeekLLM(LLM[R]):
    """
    An DeepSeek-based Language Learning Model implementation.

    This class implements the LLM interface for DeepSeek's conversation models, handling
    configuration, authentication, and async API communication.

    Parameters
    ----------
    output_model : Type[R]
        A Pydantic BaseModel subclass defining the expected response structure.
    config : LLMConfig, optional
        Configuration object containing API settings. If not provided, defaults
        will be used.
    """

    def __init__(self, output_model: T.Type[R], config: T.Optional[LLMConfig] = None):
        """
        Initialize the DeepSeek LLM instance.

        Parameters
        ----------
        output_model : Type[R]
            Pydantic model class for response validation.
        config : LLMConfig, optional
            Configuration settings for the LLM.
        """
        super().__init__(output_model, config)

        base_url = config.base_url or "https://api.openmind.org/api/core/deepseek"

        if config.api_key is None or config.api_key == "":
            raise ValueError("config file missing api_key")
        else:
            api_key = config.api_key

        client_kwargs = {}
        client_kwargs["base_url"] = base_url
        client_kwargs["api_key"] = api_key

        self._client = openai.OpenAI(**client_kwargs)

    async def ask(self, prompt: str) -> R | None:
        """
        Send a prompt to the DeepSeek API and get a structured response.

        Parameters
        ----------
        prompt : str
            The input prompt to send to the model.

        Returns
        -------
        R or None
            Parsed response matching the output_model structure, or None if
            parsing fails.
        """
        try:
            logging.debug(f"DeepSeek LLM input: {prompt}")
            self.io_provider.llm_start_time = time.time()
            self.io_provider.set_llm_prompt(prompt)

            messages = [
                {
                    "role": "system",
                    "content": f"You must respond with valid JSON matching this schema: {self._output_model.model_json_schema()}",
                },
                {"role": "user", "content": prompt},
            ]

            parsed_response = self._client.chat.completions.create(
                model=(
                    "deepseek-chat"
                    if self._config.model is None
                    else self._config.model
                ),
                messages=messages,
                response_format={"type": "json_object"},
            )

            message_content = parsed_response.choices[0].message.content
            self.io_provider.llm_end_time = time.time()

            try:
                parsed_response = self._output_model.model_validate_json(
                    message_content
                )
                logging.debug(f"LLM output: {parsed_response}")
                return parsed_response
            except Exception as e:
                logging.error(f"Error parsing response: {e}")
                return None
        except Exception as e:
            logging.error(f"Error asking LLM: {e}")
            return None
