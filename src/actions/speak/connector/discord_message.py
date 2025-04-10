import logging
import asyncio

from actions.base import ActionConfig, ActionConnector
from actions.speak.interface import SpeakInput

# Global registry for active Discord clients
_DISCORD_INSTANCES = []

def register_discord_client(discord_client):
    """Register a Discord client instance for sending messages."""
    if discord_client not in _DISCORD_INSTANCES:
        _DISCORD_INSTANCES.append(discord_client)
        logging.info("Discord client registered for sending messages")

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
        
        # Send to registered Discord instances if available
        for discord_client in _DISCORD_INSTANCES:
            try:
                await discord_client.send_message(message)
                logging.info(f"Message sent to Discord: {message}")
                return  # Stop after first successful send
            except Exception as e:
                logging.error(f"Error sending to Discord: {e}")
