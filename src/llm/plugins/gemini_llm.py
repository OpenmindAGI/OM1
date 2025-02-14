import logging
import time
import typing as T

import openai
from pydantic import BaseModel

from llm import LLM, LLMConfig
from providers.io_provider import IOProvider

R = T.TypeVar("R", bound=BaseModel)


class GeminiLLM(LLM[R]):
    """
    Google Gemini LLM implementation using OpenAI-compatible API.

    Handles authentication and response parsing for Gemini endpoints.
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

        base_url = config.base_url or "https://api.openmind.org/api/core/gemini"

        if config.api_key is None or config.api_key == "":
            raise ValueError("config file missing api_key")
        else:
            api_key = config.api_key

        client_kwargs = {}
        client_kwargs["base_url"] = base_url
        client_kwargs["api_key"] = api_key

        # Initialize OpenAI-compatible client
        logging.info(f"Initializing Gemini OpenAI client with {client_kwargs}")
        self._client = openai.AsyncOpenAI(**client_kwargs)
        self.io_provider = IOProvider()

    async def ask(self, prompt: str) -> R | None:
        """
        Execute LLM query and parse response

        Parameters
        ----------
        prompt : str
            Input prompt for the LLM
        """
        try:
            self.io_provider.llm_start_time = time.time()
            self.io_provider.set_llm_prompt(prompt)
            response = await self._execute_api_request(prompt)
            logging.debug(f"Gemini raw response: {response}")
            self.io_provider.llm_end_time = time.time()
            return self._parse_response(response)

        except Exception as error:
            logging.error(f"Gemini API error: {error}")
            return None

    async def _execute_api_request(self, prompt: str):
        """
        Execute the actual API call to Gemini

        Parameters
        ----------
        prompt : str
            Input prompt for the LLM
        """
        completion = await self._client.chat.completions.create(
            model=(
                "gemini-2.0-flash-exp"
                if self._config.model is None
                else self._config.model
            ),
            messages=self._build_messages(prompt),
            response_format={"type": "json_object"},
        )
        return completion

    def _build_messages(self, prompt: str) -> list[dict]:
        """
        Construct message payload for API request

        Parameters
        ----------
        prompt : str
            Input prompt for the LLM

        Returns
        -------
        list[dict]
            List of messages to send to the API
        """
        system_message = {
            "role": "system",
            "content": f"Respond with valid JSON matching this schema: {self._output_model.model_json_schema()}",
        }
        return [system_message, {"role": "user", "content": prompt}]

    def _parse_response(self, response: openai.ChatCompletion) -> R | None:
        """
        Parse the response from the API

        Parameters
        ----------
        response


        Returns
        -------
        R | None
            Parsed response matching the output_model structure, or None if
            parsing fails.
        """

        try:
            content = response.choices[0].message.content
            logging.debug(f"Gemini output: {content}")
            parsed = self._output_model.model_validate_json(content)
            logging.debug(f"Gemini output parsed: {parsed}")
            return parsed
        except Exception as error:
            logging.error(f"Failed to parse Gemini response: {error}")
            return None
