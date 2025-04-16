import asyncio
import logging
from queue import Empty, Queue
from typing import AsyncIterator, List, Optional, Dict, Any, Union

# Import discord.py
import discord
from discord.ext import commands

from inputs.base import SensorConfig
from inputs.base.loop import FuserInput

class DiscordInput(FuserInput[str]):
    """Discord integration input handler for chatting with OM1."""

    def __init__(
        self,
        config: Optional[SensorConfig] = None,
    ):
        """Initialize DiscordInput with configuration.

        Parameters
        ----------
        config : Optional[SensorConfig]
            Configuration object from the runtime
        """
        if config is None:
            config = SensorConfig()

        super().__init__(config)

        self.buffer: List[str] = []
        self.message_buffer: Queue[str] = Queue()
        self.bot_token = getattr(config, "bot_token", None)
        self.channel_id = getattr(config, "channel_id", None)
        self.message_history: List[Dict[str, Any]] = []
        # Flag to track if the last received message mentioned the bot
        self.last_message_was_mention = False
        
        # Create Discord client with all intents
        intents = discord.Intents.default()
        intents.message_content = True  # Need to enable this to read message content
        intents.members = True          # Enable access to member objects in messages for mention detection
        self.bot = commands.Bot(command_prefix="!", intents=intents)
        self.is_running = False
        
        # Setup is_registered flag for action connector
        self.is_registered = False
        
        # Set up bot event handlers
        @self.bot.event
        async def on_ready():
            logging.info(f"Logged in as {self.bot.user}")
            logging.info(f"Monitoring channel: {self.channel_id}")
            self.is_running = True
            
        @self.bot.event
        async def on_message(message):
            # Ignore messages from the bot itself
            if message.author == self.bot.user:
                return
                
            # Only process messages from the specified channel if configured
            if self.channel_id and str(message.channel.id) != str(self.channel_id):
                return
            
            # Check if the bot is mentioned in the message or if it's a direct message
            is_mentioned = self.bot.user in message.mentions or isinstance(message.channel, discord.DMChannel)
            
            # Update the mention flag
            self.last_message_was_mention = is_mentioned
            
            # Store the message in history
            self.message_history.append({
                "author": message.author.name,
                "content": message.content,
                "is_bot": False,
                "mentioned_bot": is_mentioned
            })
            
            # Only process messages when the bot is mentioned
            if is_mentioned:
                # Add message to buffer, indicating the bot was mentioned
                msg_content = f"{message.author.name}: {message.content}"
                self.message_buffer.put_nowait(msg_content)
                self.buffer.append(msg_content)
                logging.info(f"Received message with mention: {msg_content}")
            else:
                # Log message without adding to buffer
                logging.debug(f"Skipping message without mention: {message.author.name}: {message.content}")
            
            # No longer automatically process commands - only respond to mentions
            if is_mentioned:
                await self.bot.process_commands(message)
            
            # Print conversation log after each message
            self.print_conversation_log()

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.is_running:
            await self.bot.close()

    def print_conversation_log(self):
        """Print the current conversation log to the console."""
        print("\n=== CONVERSATION LOG ===")
        for idx, msg in enumerate(self.message_history):
            source = "BOT" if msg.get("is_bot", False) else "USER"
            mention_indicator = " [MENTIONED]" if msg.get("mentioned_bot", False) else ""
            print(f"[{idx+1}] [{source}]{mention_indicator} {msg['author']}: {msg['content']}")
        print("========================\n")

    async def raw_to_text(self, raw_input: Optional[str] = None) -> str:
        """Convert raw input to text format and add to buffer.

        Parameters
        ----------
        raw_input : Optional[str]
            Raw input to process. If None, process from message buffer.

        Returns
        -------
        str
            The processed text
        """
        if raw_input:
            self.message_buffer.put_nowait(raw_input)

        if not self.message_buffer.empty():
            try:
                message = self.message_buffer.get_nowait()
                if message:
                    if message not in self.buffer:
                        self.buffer.append(message)
                    logging.debug(f"Processing message: {message}")
                    return message
            except Empty:
                pass

        return ""

    async def start(self) -> None:
        """Start the Discord bot."""
        if not self.bot_token:
            logging.error("Discord bot token not provided")
            return
            
        logging.info(f"Starting Discord bot with token: {self.bot_token[:5]}...")
        
        # Start Discord bot in background task
        asyncio.create_task(self.bot.start(self.bot_token))
        
        # Wait for bot to be ready
        start_time = asyncio.get_event_loop().time()
        while not self.is_running:
            await asyncio.sleep(0.1)
            # Timeout after 30 seconds
            if asyncio.get_event_loop().time() - start_time > 30:
                logging.error("Timed out waiting for Discord bot to start")
                return
                
        # Try to register with action connector if it's available
        try:
            # Attempt to import and register without creating a hard dependency
            module = __import__('actions.speak.connector.discord_message', fromlist=['register_discord_client'])
            register_func = getattr(module, 'register_discord_client', None)
            if register_func:
                register_func(self)
                self.is_registered = True
                logging.info("Discord input registered with connector")
        except (ImportError, AttributeError):
            logging.warning("Discord message connector not available, bot won't respond automatically")

    async def listen(self) -> AsyncIterator[str]:
        """Listen for new Discord messages."""
        await self.start()

        while True:
            message = await self._poll()
            if message:
                yield message
            await asyncio.sleep(0.1)

    async def _poll(self) -> Optional[str]:
        """Poll for new messages."""
        await asyncio.sleep(0.5)
        try:
            message = self.message_buffer.get_nowait()
            return message
        except Empty:
            return None
            
    async def send_message(self, content: str) -> bool:
        """Send a message to the configured Discord channel.
        
        This method is maintained for compatibility with the action connector.
        Only sends messages in response to mentions.
        
        Parameters
        ----------
        content : str
            The message content to send
            
        Returns
        -------
        bool
            Whether the message was sent successfully
        """
        # Don't send a message if the last message didn't mention the bot
        if not self.last_message_was_mention:
            logging.info("Ignoring message send request - last message didn't mention the bot")
            return False
            
        if not self.is_running:
            logging.error("Discord bot is not running")
            return False
            
        try:
            if not self.channel_id:
                logging.error("No channel_id configured")
                return False
            
            # Try to convert channel_id to integer with proper error handling
            try:
                channel_id_int = int(self.channel_id)
                channel = self.bot.get_channel(channel_id_int)
                
                if not channel:
                    # Try to fetch the channel if not found in cache
                    try:
                        channel = await self.bot.fetch_channel(channel_id_int)
                    except discord.NotFound:
                        logging.error(f"Channel {self.channel_id} not found")
                        return False
                    except discord.Forbidden:
                        logging.error(f"No permission to access channel {self.channel_id}")
                        return False
                    except discord.HTTPException as e:
                        logging.error(f"Failed to fetch channel {self.channel_id}: {str(e)}")
                        return False
            except ValueError:
                logging.error(f"Channel ID '{self.channel_id}' is not a valid integer")
                return False
                    
            if channel:
                await channel.send(content)
                
                # Store bot message in history
                self.message_history.append({
                    "author": self.bot.user.name if self.bot.user else "Bot",
                    "content": content,
                    "is_bot": True
                })
                
                # Reset the mention flag after sending a response
                self.last_message_was_mention = False
                
                logging.info(f"Sent message: {content}")
                self.print_conversation_log()
                return True
            return False
        except Exception as e:
            logging.error(f"Error sending message: {str(e)}")
            return False

    def formatted_latest_buffer(self) -> Optional[str]:
        """Format and return the conversation context."""
        if not self.buffer:
            return None

        # Only return the most recent message to the agent
        if len(self.buffer) > 0:
            content = self.buffer[-1]
        else:
            content = ""

        result = f"""
DiscordInput CONVERSATION
// START
{content}
// END
"""
        return result

    async def initialize_with_query(self, query: str) -> None:
        """Initialize with a query - not used for Discord but required by interface
        
        Parameters
        ----------
        query : str
            The query to initialize with
        """
        logging.info(f"[DiscordInput] Initializing with query: {query}")
        
        # Store system message in history
        self.message_history.append({
            "author": "System",
            "content": query,
            "is_bot": True
        })
        
        self.message_buffer.put_nowait(f"System: {query}")
        self.print_conversation_log()