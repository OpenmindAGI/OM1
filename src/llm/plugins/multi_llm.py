import json
import logging
import time
import typing as T

import aiohttp
from pydantic import BaseModel, Field

from llm import LLM, LLMConfig

R = T.TypeVar("R", bound=BaseModel)


class ApiCommand(BaseModel):
    """Command format returned by the robotic_team API."""

    command: str = Field(..., description="The command type")
    args: T.Optional[str] = Field(None, description="Optional command arguments")


class RoboticTeamResponse(BaseModel):
    """Response model from the robotic team endpoint"""

    content: T.Optional[str] = Field(
        None, description="Text content in markdown format"
    )
    structured_output: T.Optional[dict] = Field(
        None, description="Structured output data"
    )
    commands: T.Optional[list[ApiCommand]] = Field(
        None, description="List of commands to execute"
    )


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
        
        # Store structured_outputs flag from config
        self.structured_outputs = getattr(config, "structured_outputs", True)

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
                "content": f"You are a robotic control system. Respond with valid structured output for these commands. Output schema: {json.dumps(self._output_model.model_json_schema(), indent=2)}"
            }
            
            # Add system message at the beginning
            all_messages = [system_message]
            if messages:
                all_messages.extend(messages)
            all_messages.append({"role": "user", "content": prompt})

            # Prepare request data
            request = {
                "message": prompt,
                "model": self._config.model,
                "messages": all_messages,
                "response_model": self._output_model.model_json_schema(),
                "structured_outputs": self.structured_outputs,
            }

            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {self._config.api_key}"}

                logging.debug(f"Sending request to {self.endpoint}")

                # Send request to endpoint
                async with session.post(
                    self.endpoint,
                    json=request,
                    headers=headers,
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logging.error(
                            f"API request failed with status {response.status}: {error_text}"
                        )
                        return None

                    response_json = await response.json()
                    self.io_provider.llm_end_time = time.time()
                    logging.debug(f"Raw response: {response_json}")

                    # First try the structured_output field
                    if "structured_output" in response_json and response_json["structured_output"]:
                        try:
                            parsed_response = self._output_model.model_validate(
                                response_json["structured_output"]
                            )
                            logging.debug(f"MultiLLM structured output: {parsed_response}")
                            return parsed_response
                        except Exception as e:
                            logging.error(f"Error validating structured response: {e}")
                    
                    # Then try content field - parse commands from markdown/text
                    if "content" in response_json and response_json["content"]:
                        try:
                            # Attempt to extract commands from content
                            content = response_json["content"]
                            
                            # Try to find a JSON blob in the content
                            import re
                            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
                            if json_match:
                                json_str = json_match.group(1)
                                parsed_json = json.loads(json_str)
                                if isinstance(parsed_json, dict):
                                    parsed_response = self._output_model.model_validate(parsed_json)
                                    logging.debug(f"MultiLLM JSON from content: {parsed_response}")
                                    return parsed_response
                            
                            # Try creating a simple output directly matching schema
                            schema = self._output_model.model_json_schema()
                            if "properties" in schema and "commands" in schema["properties"]:
                                # Attempt to parse commands from content
                                command_lines = [line.strip() for line in content.split('\n') 
                                                if line.strip().startswith('-') or line.strip().startswith('*')]
                                
                                if command_lines:
                                    commands = []
                                    for line in command_lines:
                                        # Remove list marker
                                        cmd_text = line.lstrip('-* ').strip()
                                        if ':' in cmd_text:
                                            cmd_parts = cmd_text.split(':', 1)
                                            cmd_type = cmd_parts[0].strip()
                                            cmd_value = cmd_parts[1].strip()
                                            commands.append({"type": cmd_type, "value": cmd_value})
                                        else:
                                            # Just use the text as is - split into verb and object if possible
                                            words = cmd_text.split()
                                            if len(words) > 1:
                                                cmd_type = words[0]
                                                cmd_value = ' '.join(words[1:])
                                                commands.append({"type": cmd_type, "value": cmd_value})
                                
                                    if commands:
                                        result = {"commands": commands}
                                        parsed_response = self._output_model.model_validate(result)
                                        logging.debug(f"MultiLLM parsed commands: {parsed_response}")
                                        return parsed_response
                        
                            logging.error("Could not parse commands from content")
                        except Exception as e:
                            logging.error(f"Error processing content response: {e}")
                    
                    # Try commands field as last resort
                    if "commands" in response_json and response_json["commands"]:
                        try:
                            commands = []
                            for cmd in response_json["commands"]:
                                if isinstance(cmd, dict) and "command" in cmd:
                                    cmd_type = cmd["command"]
                                    cmd_value = cmd.get("args", "")
                                    commands.append({"type": cmd_type, "value": cmd_value})
                            
                            if commands:
                                result = {"commands": commands}
                                parsed_response = self._output_model.model_validate(result)
                                logging.debug(f"MultiLLM command output: {parsed_response}")
                                return parsed_response
                        except Exception as e:
                            logging.error(f"Error processing commands: {e}")
                    
                    # Create a minimal valid response as fallback
                    try:
                        # Last resort - create a minimal valid output
                        schema = self._output_model.model_json_schema()
                        if "properties" in schema and "commands" in schema["properties"]:
                            # Create a basic command from the prompt
                            words = prompt.split()
                            if len(words) >= 2:
                                cmd_type = words[0].lower()
                                cmd_value = ' '.join(words[1:])
                                result = {"commands": [{"type": cmd_type, "value": cmd_value}]}
                                parsed_response = self._output_model.model_validate(result)
                                logging.debug(f"MultiLLM fallback output: {parsed_response}")
                                return parsed_response
                    except Exception as e:
                        logging.error(f"Error creating fallback response: {e}")

                    logging.error("Failed to create a valid response after trying all methods")
                    return None

        except Exception as e:
            logging.error(f"Error during API request: {str(e)}")
            return None
