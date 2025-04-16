import logging
from actions.base import ActionConfig, ActionConnector
from actions.speak.interface import SpeakInput

# Global reference for the active Discord client
_DISCORD_CLIENT = None

def register_discord_client(discord_client) -> None:
    """Register a Discord client instance for sending messages."""
    global _DISCORD_CLIENT
    _DISCORD_CLIENT = discord_client
    logging.info("Discord client registered for sending messages")

class DiscordMessageConnector(ActionConnector[SpeakInput]):
    """Connector for sending messages to Discord."""

    def __init__(self, config: ActionConfig) -> None:
        super().__init__(config)

    async def connect(self, output_interface: SpeakInput) -> None:
        """Send message to Discord if available."""
        message = output_interface.action
        logging.info(f"SendThisToDiscord: {message}")
        
        if _DISCORD_CLIENT is None:
            logging.warning("No Discord client registered, cannot send message")
            return
            
        try:
            # Client has its own send_message implementation
            result = await _DISCORD_CLIENT.send_message(message)
            if result:
                logging.info(f"Message sent to Discord successfully")
        except Exception as e:
            logging.error(f"Error sending to Discord: {e}")
