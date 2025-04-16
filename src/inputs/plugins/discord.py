import asyncio
import logging
from queue import Empty, Queue
from typing import AsyncIterator, List, Optional, Dict, Any

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

        # Message handling attributes
        self.buffer: List[str] = []
        self.message_buffer: Queue[str] = Queue()
        self.message_history: List[Dict[str, Any]] = []
        self.last_message_was_mention = False
        
        # Configuration attributes
        self.bot_token = getattr(config, "bot_token", None)
        self.channel_id = getattr(config, "channel_id", None)
        
        # Bot setup
        self.is_running = False
        self.is_registered = False
        self._setup_bot()
        
    def _setup_bot(self):
        """Set up the Discord bot with proper intents and event handlers."""
        # Create Discord client with required intents
        intents = discord.Intents.default()
        intents.message_content = True  # Need to enable this to read message content
        intents.members = True          # Enable access to member objects in messages for mention detection
        self.bot = commands.Bot(command_prefix="!", intents=intents)
        
        # Set up bot event handlers
        @self.bot.event
        async def on_ready():
            logging.info(f"Logged in as {self.bot.user}")
            logging.info(f"Monitoring channel: {self.channel_id}")
            self.is_running = True
            
        @self.bot.event
        async def on_message(message):
            await self._handle_message(message)
    
    async def _handle_message(self, message):
        """Process an incoming Discord message.
        
        Parameters
        ----------
        message : discord.Message
            The Discord message to process
        """
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
            
            # Process commands if bot was mentioned
            await self.bot.process_commands(message)
        else:
            # Log message without adding to buffer
            logging.debug(f"Skipping message without mention: {message.author.name}: {message.content}")
        
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
                if message and message not in self.buffer:
                    self.buffer.append(message)
                    logging.debug(f"Processing message: {message}")
                return message or ""
            except Empty:
                pass

        return ""

    async def start(self) -> None:
        """Start the Discord bot and register with the action connector."""
        if not self.bot_token:
            logging.error("Discord bot token not provided")
            return
            
        logging.info(f"Starting Discord bot with token: {self.bot_token[:5]}...")
        
        # Start Discord bot in background task
        asyncio.create_task(self.bot.start(self.bot_token))
        
        # Wait for bot to be ready with timeout
        await self._wait_for_bot_ready()
        
        # Register with action connector if successfully started
        if self.is_running:
            await self._register_with_connector()

    async def _wait_for_bot_ready(self, timeout_seconds: int = 30) -> None:
        """Wait for the bot to be ready with a timeout.
        
        Parameters
        ----------
        timeout_seconds : int
            Maximum time to wait in seconds
        """
        start_time = asyncio.get_event_loop().time()
        while not self.is_running:
            await asyncio.sleep(0.1)
            # Timeout after specified seconds
            if asyncio.get_event_loop().time() - start_time > timeout_seconds:
                logging.error(f"Timed out waiting for Discord bot to start after {timeout_seconds} seconds")
                return
    
    async def _register_with_connector(self) -> None:
        """Register this client with the action connector."""
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
            
        if not self.channel_id:
            logging.error("No channel_id configured")
            return False
        
        try:
            channel = await self._get_channel()
            if not channel:
                return False
                
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
        except Exception as e:
            logging.error(f"Error sending message: {str(e)}")
            return False
    
    async def _get_channel(self) -> Optional[discord.abc.Messageable]:
        """Get the Discord channel for sending messages.
        
        Returns
        -------
        Optional[discord.abc.Messageable]
            The channel object or None if not found/accessible
        """
        try:
            channel_id_int = int(self.channel_id)
            channel = self.bot.get_channel(channel_id_int)
            
            if not channel:
                # Try to fetch the channel if not found in cache
                try:
                    channel = await self.bot.fetch_channel(channel_id_int)
                except discord.NotFound:
                    logging.error(f"Channel {self.channel_id} not found")
                    return None
                except discord.Forbidden:
                    logging.error(f"No permission to access channel {self.channel_id}")
                    return None
                except discord.HTTPException as e:
                    logging.error(f"Failed to fetch channel {self.channel_id}: {str(e)}")
                    return None
            return channel
        except ValueError:
            logging.error(f"Channel ID '{self.channel_id}' is not a valid integer")
            return None

    def formatted_latest_buffer(self) -> Optional[str]:
        """Format and return the conversation context."""
        if not self.buffer:
            return None

        # Only return the most recent message to the agent
        content = self.buffer[-1] if self.buffer else ""

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