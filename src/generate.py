import aiohttp
import json
import os

async def generate_response(self, conversation_log):
    """
    Generate a response using the OpenMind API based on the conversation log.
    
    Args:
        conversation_log: A list of message objects with role, content, and name
        
    Returns:
        A string containing the model's response
    """
    # Get API key from environment variable
    api_key = os.getenv("OM_API_KEY")
    if not api_key:
        raise ValueError("OM_API_KEY environment variable is not set")
    
    # Get provider from config or environment variable
    provider = os.getenv("OPENMIND_PROVIDER", "openai")  # Default to openai if not specified
    
    # Get model from config or environment variable
    model = os.getenv("OPENMIND_MODEL", "gpt-4o")  # Default to gpt-4o if not specified
    
    # Format the conversation for the OpenMind API
    url = f"https://api.openmind.org/api/core/{provider}/chat/completions"
    
    # Prepare the payload
    payload = {
        "model": model,
        "messages": conversation_log
    }
    
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }
    
    # Make the API request
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"API request failed with status {response.status}: {error_text}")
            
            response_data = await response.json()
            
            # Extract the response text from the API response
            # The exact structure depends on the API response format
            try:
                # Assuming the response format is similar to OpenAI's
                return response_data["choices"][0]["message"]["content"]
            except (KeyError, IndexError) as e:
                raise Exception(f"Failed to parse API response: {e}. Response: {response_data}")