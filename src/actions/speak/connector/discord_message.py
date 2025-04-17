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
            result = await self._send_discord_message(message)
            if not result:
                logging.warning("Failed to send message to Discord")
        except Exception as e:
            logging.error(f"Error sending to Discord: {e}")
            
    async def _send_discord_message(self, content: str) -> bool:
        """Send a message to the Discord channel.
        
        Parameters
        ----------
        content : str
            The message content to send
            
        Returns
        -------
        bool
            Whether the message was sent successfully
        """
        if _DISCORD_CLIENT is None:
            return False
            
        bot = _DISCORD_CLIENT.bot
        channel_id = _DISCORD_CLIENT.channel_id
        
        # Check if the bot was mentioned in the last message
        if not hasattr(_DISCORD_CLIENT, 'last_message_was_mention') or not _DISCORD_CLIENT.last_message_was_mention:
            logging.info("Ignoring message send request - bot wasn't mentioned")
            return False
        
        if bot is None or channel_id is None:
            logging.error("Missing bot or channel_id in Discord info")
            return False
            
        if not bot.is_ready():
            logging.error("Discord bot is not running")
            return False
        
        try:
            channel = await self._get_channel(bot, channel_id)
            if not channel:
                return False
                
            await channel.send(content)
            logging.info(f"Message sent to Discord channel {channel_id}")
            
            # Reset the mention status after sending a message
            if hasattr(_DISCORD_CLIENT, 'reset_mention_status'):
                _DISCORD_CLIENT.reset_mention_status()
                
            return True
        except Exception as e:
            logging.error(f"Error sending message to Discord: {e}")
            return False
            
    async def _get_channel(self, bot, channel_id: str):
        """Get the Discord channel for sending messages.
        
        Parameters
        ----------
        bot : Bot
            The Discord bot instance
        channel_id : str
            The channel ID to get
            
        Returns
        -------
        Channel or None
            The channel object or None if not found/accessible
        """
        try:
            channel_id_int = int(channel_id)
            channel = bot.get_channel(channel_id_int)
            
            if not channel:
                # Try to fetch the channel if not found in cache
                try:
                    channel = await bot.fetch_channel(channel_id_int)
                except Exception as not_found:
                    logging.error(f"Channel {channel_id} not found: {not_found}")
                    return None
            return channel
        except ValueError:
            logging.error(f"Channel ID '{channel_id}' is not a valid integer")
            return None
