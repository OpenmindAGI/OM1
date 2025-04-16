import logging
import asyncio
from typing import Dict, Any, Union, Optional, List

from actions.base import ActionConfig, ActionConnector
from actions.speak.interface import SpeakInput

# Global registry for active Discord clients
_DISCORD_INSTANCES = []

def get_discord_clients():
    """Get registered Discord clients."""
    return _DISCORD_INSTANCES

def register_discord_client(discord_client):
    """Register a Discord client instance for sending messages."""
    if discord_client not in _DISCORD_INSTANCES:
        _DISCORD_INSTANCES.append(discord_client)
        logging.info("Discord client registered for sending messages")

async def send_message_to_discord(content: str) -> bool:
    """Send a message to registered Discord clients.
    
    Parameters
    ----------
    content : str
        The message content to send
        
    Returns
    -------
    bool
        Whether the message was sent successfully
    """
    success = False
    for discord_client in _DISCORD_INSTANCES:
        try:
            # Each client has its own send_message implementation
            result = await discord_client.send_message(content)
            if result:
                success = True
                logging.info(f"Message sent to Discord: {content}")
        except Exception as e:
            logging.error(f"Error sending to Discord: {e}")
    
    return success

class DiscordMessageConnector(ActionConnector[SpeakInput]):
    """Connector for sending messages to Discord."""

    def __init__(self, config: ActionConfig):
        super().__init__(config)

    async def connect(self, output_interface: SpeakInput) -> None:
        """Send message to Discord if available."""
        message = output_interface.action
        logging.info(f"Processing Discord message: {message}")
        
        # Log the message regardless
        logging.info(f"SendThisToDiscord: {message}")
        
        # Send message to Discord
        await send_message_to_discord(message)

    async def speak(self, text: Union[str, Dict[str, Any]]) -> bool:
        """Handle speaking action by sending to Discord.
        
        Parameters
        ----------
        text : Union[str, Dict[str, Any]]
            The text to send or a dictionary containing an 'action' key
            
        Returns
        -------
        bool
            Whether the message was sent successfully
        """
        if isinstance(text, dict) and 'action' in text:
            # Handle when receiving dict from passthrough
            content = text['action']
        else:
            # Handle direct string input
            content = text
            
        # Actually send the message
        success = await send_message_to_discord(content)
        logging.info(f"Discord message sent: {content}, success: {success}")
        return success
